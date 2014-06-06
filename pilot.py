
import json
import requests
import logging
import time

logger = logging.getLogger('pilot')

class PilotException(Exception):
	pass

class Pilot(object):

	_WAIT_SLEEP_TIME = 5

	def __init__(self, baseUrl):
		self.baseUrl = baseUrl.strip('/')


	def _wait_for_task_finished(self, taskInfo=None):
		finished = False
		while not finished:
			r = requests.get('%s/status' % self.baseUrl)
			if (r.status_code != 200):
				raise PilotException('unable to get pilot status from device: %s' % r.text)
			status = json.loads(r.text)
			if 'taskRunning' not in status:
				raise PilotException('Invalid Pilot status: %s' % r.text)

			# check if finished
			if status['taskRunning'] == False:
				finished = True

			# check if the next job is already running
			elif taskInfo and status['taskInfo'] != taskInfo:
				finished = True

			else:
				logger.debug('waiting for task to finish...')
				time.sleep(Pilot._WAIT_SLEEP_TIME)
		logger.info('task finished.')


	def installed_applications(self):
		r = requests.get('%s/applications' % self.baseUrl)
		if (r.status_code != 200):
			raise PilotException('unable to get list of installed apps from device: %s' % r.text)
		apps = json.loads(r.text)
		if not apps:
			return {}
		return apps


	def install_appstore(self, appInfo, accountIdentifier, taskInfo={}):
		''' this method will return if the app download was successfully initiated (probably the app will not yet be fully installed)
		'''

		## add some debugging data
		taskInfo.update({'worker_action':'install_appstore'})

		## appInfo contains store data and thus the bundleID key is 'bundle-id'!!
		if 'bundle-id' in appInfo:
			bundleId = appInfo['bundle-id']
			if bundleId in self.installed_applications():
				raise PilotException('App already installed! <%s>' % bundleId)

		data = {
			'appInfo': appInfo,
			'accountIdentifier': accountIdentifier,
			'taskInfo': taskInfo
		}
		r = requests.post("%s/install/appstore" % self.baseUrl, data=json.dumps(data))
		if (r.status_code != 200):
			logger.error("Initiating install failed! Response: %s" % r.text)
			return False

		self._wait_for_task_finished()

		result = True
		if 'bundle-id' in appInfo:
			result = appInfo['bundle-id'] in self.installed_applications()
		return result


	def install_cydia(self, bundleId, taskInfo={}):
		data = {
			'bundleId': bundleId,
			'taskInfo': taskInfo
		}
		r = requests.post("%s/install/cydia" % self.baseUrl, data=json.dumps(data))
		if (r.status_code != 200):
			logger.error("Install failed! Response: %s" % r.text)
			return False
		return True

	def open(self, bundleId, taskInfo={}):
		data = {
			'taskInfo': taskInfo
		}
		r = requests.post("%s/open/%s" % (self.baseUrl, bundleId), data=json.dumps(data))
		if (r.status_code != 200):
			logger.error("Open failed! <%s> Response: %s" % (bundleId, r.text))


	def run_auto_execution(self, bundleId, taskInfo={}):
		logger.info('starting execution of %s', bundleId)
		taskInfo['bundleId'] = bundleId
		data = {
			'taskInfo': taskInfo
		}
		r = requests.post("%s/execute/%s" % (self.baseUrl, bundleId), data=json.dumps(data))
		if (r.status_code != 200):
			logger.error("Open failed! <%s> Response: %s" % (bundleId, r.text))
			return False

		## wait until the execution has finished
		self._wait_for_task_finished(taskInfo=taskInfo)
		logger.info('execution of %s finished', bundleId)
		return True




	def inject(self, process, command, taskInfo={}):
		data = {
			'process': process,
			'command': command,
			'taskInfo': taskInfo
		}
		r = requests.post("%s/inject" % self.baseUrl, data=json.dumps(data))
		if (r.status_code != 200):
			logger.error("Inject failed! Response: %s" % r.text)
			return None
		return json.loads(r.text)

