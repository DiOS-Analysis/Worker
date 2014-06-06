import SocketServer
import logging
from multiprocessing import Process, Manager, Event, log_to_stderr

from python_client import SocketRelay, ThreadedTCPServer, USBMux, MuxError


_LOGGER = log_to_stderr()
_JOIN_TIMEOUT = 5

class DeviceTCPRelay(SocketServer.BaseRequestHandler):

	def handle(self):
		if self.server.stopped():
			return

		if not self.server.muxdev:
			_LOGGER.error("Device invalid")
			self.request.close()
			return

		_LOGGER.debug("Connecting to device %s" % str(self.server.muxdev))
		dsock = None
		try:
			dsock = self.server.mux.connect(self.server.muxdev, self.server.rport)
		except MuxError:
			_LOGGER.warning("Connection to device %s died!" % str(self.server.muxdev))
			if self.request:
				self.request.close()
			return
		lsock = self.request
		_LOGGER.debug("Connection established, relaying data")
		try:
			fwd = SocketRelay(dsock, lsock)
				#, self.server.bufsize * 1024)
			fwd.handle()
		finally:
			dsock.close()
			lsock.close()
		_LOGGER.debug("Connection closed")



class DeviceServer(ThreadedTCPServer, Process):
	
	#causes handle_request to return
	timeout = 1
	
	def __init__(self, mux, muxdevice, server_address, RequestHandlerClass):
		Process.__init__(self)
		ThreadedTCPServer.__init__(self, server_address, RequestHandlerClass)
		self.mux = mux
		self.muxdev = muxdevice
		self._stop = Event()

	def stop(self):
		self._stop.set()
		
	def stopped(self):
		return self._stop.is_set()

	def run(self):
		if self.stopped():
			_LOGGER.warning("Thread already stopped")
		
		while not self.stopped():
			self.handle_request()
		self.socket.close()
		_LOGGER.debug("%s will exit now" % (str(self)))


class DeviceConnectionHandler(Process):
			
	def __init__(self):
		super(DeviceConnectionHandler, self).__init__()
		self._stop = Event()
		self.manager = Manager()
		
		# devices: dont read that field after start() (will be empty)
		self.devices = {}
		# a managed dict to sync changes between threads
		self.device_id_map = self.manager.dict()
		
		self.mux = USBMux()	


	def handle(self):
		""" Start device handling. Will not return until calling stop() """
				
		if not self.mux.devices:
			self.mux.process(1.0)
		
		while not self.stopped():
			muxdevs = self.mux.devices
	#		print muxdevs
	
			#create new device handlers
			for dev in muxdevs:
				if dev not in self.devices:
					_LOGGER.info("New Device: %s" % str(dev))
					
					# create device connection tunnel via usbmux
					server = DeviceServer(self.mux, dev, ('localhost', 0), DeviceTCPRelay)
					server.rport = 8080

					server.start()
					self.devices[dev] = server
					self.device_id_map[dev.serial] = server.server_address
					
					_LOGGER.debug("Serving device %s via %s" % (str(dev), server.server_address))
	
					
			#remove invalid devices
			for dev in self.devices.keys():
				if dev not in muxdevs:
					_LOGGER.info("Device gone: %s" % str(dev))
					_LOGGER.debug("Server: %s" % server)
					server.stop()
					server.join(_JOIN_TIMEOUT)
					_LOGGER.debug("Server stopped: %s" % server)
					self.devices.pop(dev)
					self.device_id_map.pop(dev.serial)
			
			#check for new devices, ...
			self.mux.process(0.1)
			
			

	def stop(self):
		self._stop.set()
		
	def stopped(self):
		return self._stop.is_set()

	def run(self):
		self.handle()
		
		_LOGGER.debug("stopping device servers...")
		for server in self.devices.itervalues():
			server.stop()
			server.join(_JOIN_TIMEOUT)
		_LOGGER.debug("%s will exit now" % (str(self)))
		
	def device_connection_info(self, deviceUUID):
		'''Returns a tuple of ip and port'''
		if deviceUUID in self.device_id_map:
				return self.device_id_map[deviceUUID]
		else:
			return None


_SHARED_DEVICE_HANDLER = None

def shared_device_handler():
	global _SHARED_DEVICE_HANDLER
	if not _SHARED_DEVICE_HANDLER:
		_SHARED_DEVICE_HANDLER = DeviceConnectionHandler()	
		_SHARED_DEVICE_HANDLER.start()
		import time
		time.sleep(1)
	return _SHARED_DEVICE_HANDLER

