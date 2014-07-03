#!/usr/bin/python

import socket # get hostnmae
import logging
import time
import traceback
import requests

from multiprocessing import Process, Event

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('worker')

logger.setLevel(level=logging.INFO)

from job import JobFactory
from device import iDevice
from backend import Backend
#from pilot import Pilot

MIN_FREE_DEVICE_BYTES = 1024**3

class DeviceLoop(Process):

	def __init__(self, device, backend):
		super(DeviceLoop, self).__init__()
		self.device = device
		self.backend = backend
		self._stop = Event()

	def stop(self):
		self._stop.set()

	def stopped(self):
		return self._stop.is_set()

	def run(self):
		logger.info("registering device %s with backend" % str(self.device))
		self.backend.register_device(self.device)

		logger.info("entering device loop: %s" % str(self.device))
		while not self.stopped():
			
			free_bytes = self.device.free_bytes()
			if (free_bytes < MIN_FREE_DEVICE_BYTES):
				logger.error("Low disk space on device: %s (%s < %s). Stopping execution now." % (self.device, free_bytes, MIN_FREE_DEVICE_BYTES))
				#pilot = Pilot(self.device.base_url())
				#pilot.inject('SpringBoard', "") ## TODO add cycript command to reboot an idevice here
				#logger.info("Waiting for device restart (3 minutes)")
				#time.sleep(3*60)
				self.stop()
				break
			
			jobDict = self.backend.get_job_for_device(self.device.uuid)

			if jobDict:
				job = JobFactory.job_from_dict(jobDict, self.backend, self.device)
				if job:
					logger.info('Executing Job %s' % str(job))
					try:
						job.execute()
					except requests.ConnectionError as e:
						logger.error("Executing job failed: %s" % e)
						tb = traceback.format_exc()
						logger.error("traceback: %s" % tb)
						logger.error("Device loop will be stopped now.")
						self.stop()
						
					except Exception as e:
						logger.error("Executing job failed: %s" % e)
						tb = traceback.format_exc()
						logger.error("traceback: %s" % tb)
				else:
					logging.error("Invalid Job: %s created from jobDict: %s" % (job, jobDict))
			else:
				logger.info('waiting for job... (%s)' % str(self.device))
#				print jobDict
				#sleep some time
				time.sleep(30)




class Worker(Process):

	def __init__(self, backendUrl):
		super(Worker, self).__init__()
		self.name = socket.gethostname()
		self.backend = Backend(backendUrl)
		worker = self.backend.worker_for_name(self.name)
		if '_id' in worker:
			self.workerId = worker['_id']
			self.backend.workerId = self.workerId
		else:
			raise Exception('Worker has no id!!!!')
		self._stop = Event()

	def stop(self):
		self._stop.set()

	def stopped(self):
		return self._stop.is_set()

	def run(self):
 		deviceLoops = {}

		while not self.stopped():
			devices = iDevice.devices()
			currDeviceUUIDs = []
			# search for new devices
			for device in devices:
				currDeviceUUIDs.append(device.uuid)
				if device.uuid not in deviceLoops:
					dLoop = DeviceLoop(device, self.backend)
					dLoop.start()
					deviceLoops[device.uuid] = dLoop
					logger.info('Started device loop for %s', device.uuid)

			# cleanup finished processes
			for uuid in deviceLoops.keys():
				if uuid not in currDeviceUUIDs:
					dLoop = deviceLoops[uuid]
					if dLoop.is_alive():
						dLoop.stop()
						logger.info('Waiting for DeviceLoop to stop... (%s)', uuid)
						dLoop.join(10)
						if dLoop.is_alive():
							logger.info('... loop has not yet stopped. Terminating the loop now.  (%s)', uuid)
							dLoop.terminate()
					deviceLoops.pop(uuid)
					logger.info('Device loop finished: %s', uuid)
			time.sleep(5)

		logger.info('runloop is shutting down. Stoping all client processes gracefully')
		for uuid, process in deviceLoops:
			logger.info('joining device loop for device %s', uuid)
			process.join()
		logger.info('Worker has finished working...')




def main():
	import argparse

	parser = argparse.ArgumentParser(description='start a local AppAnalysis worker. All connected iDevices will be automatically detected and used as pilots.')
	parser.add_argument('-b','--backend', required=True, help='the backend url.')
	parser.add_argument('-d','--debug', action='store_true', help='enable debug output.')
	parser.add_argument('--debug-all', action='store_true', help='enable debug output (even for third-party code).')

	args = parser.parse_args()
	
	if args.debug_all:
		logging.basicConfig(level=logging.WARNING)
	if args.debug or args.debug_all:
		logger.setLevel(level=logging.DEBUG)


	logger.debug(args)
	

	worker = Worker(args.backend)
	worker.start()
	worker.join()


if __name__ == '__main__':
	main()
