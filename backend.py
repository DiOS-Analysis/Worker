import requests
import json
import logging
import shutil
import base64

from enum import Enum
#from job import Job
#from device import iDevice


logger = logging.getLogger('worker.'+__name__)

def json_serialize_ignore_type_errors(obj):
	try:
		print 'encoding: %s' % str(obj)
		return base64.b64encode(obj)
	except TypeError:
		return "##NONE_SERIALIZABLE_OBJECT##"

def jd(obj):
	data = json.dumps(obj, default=json_serialize_ignore_type_errors)
	return data


class BackendError(Exception):
	pass


class Backend(object):

	HEADERS = {'content-type': 'application/json'}
	RUN_STATE = Enum(['pending', 'running', 'finished', 'failed'])

	def  __init__(self, baseUrl):
		self.baseUrl = baseUrl.strip('/')
		self.workerId = None


	def register_device_accounts(self, device):
		logger.debug("register_device_accounts: %s", device)
		backendAccounts = self.get_accounts()
		for account in device.accounts():
			if not backendAccounts or account['uniqueIdentifier'] not in backendAccounts:
				self.post_account(account)


	# get device data and check/register with backend
	def register_device(self, device):
		logger.debug("register_device: %s", device)
		r = requests.get("%s/devices/%s" % (self.baseUrl, device.uuid))
		if (r.status_code == 404):
			self.register_device_accounts(device)
			r2 = requests.post("%s/devices" % self.baseUrl, headers=self.HEADERS, data=jd({
				'uuid': device.uuid,
				'accounts': list(str(acc['uniqueIdentifier']) for acc in device.accounts()),
				'deviceInfo': device.device_info_dict()
			}))
			if (r2.status_code != 200):
				logger.error("Unable to register new device: %s" % str(device))
				logger.debug("Response: %s" % r2.text)
				return False
		return True



	# gets the worker from backend
	# will even create a new worker if none found
	# raises a BackendError if the given name is not unique
	def worker_for_name(self, name):
		logger.debug("worker_for_name: %s", name)
		r = requests.get("%s/workers?name=%s" % (self.baseUrl, name))
		if r.status_code == 200:
			workers = json.loads(r.text)
			if len(workers) != 1:
				raise BackendError('The workers name is not unique! (%s)'%(name))
			worker = workers.values()[0]
			if not '_id' in worker:
				raise BackendError('No worker-id present!')
			return worker
		elif r.status_code == 404:
		# create a new worker
			r2 = requests.post("%s/workers" % self.baseUrl, headers=self.HEADERS, data=jd({
					'name': name
				}))
			if r2.status_code == 200:
				return self.worker_for_name(name)
			else:
				raise BackendError('Unable to create worker: %s' % r2.text)
		else:
			raise BackendError('Unknown backend error: %s' % r.text)


	def get_accounts(self):
		logger.debug("get_accounts")
		r = requests.get("%s/accounts" % self.baseUrl)
		if r.status_code == 200:
			return json.loads(r.text)
		else:
			return {}

	def post_account(self, account):
		logger.debug("post_account")
		r = requests.post("%s/accounts" % self.baseUrl, headers=self.HEADERS, data=jd(account))
		if (r.status_code != 200):
			logger.error("Unable to add new account: %s" % str(account))
			logger.debug("Response: %s" % r.text)
			return False
		return True


#	#returns:
#		200: Job object
#		204: None
#		else: False
	def get_job_for_device(self, deviceUUID):
		logger.debug("get_job_for_device: %s", deviceUUID)
		r = requests.get("%s/jobs/getandsetworker/%s/device/%s" % (self.baseUrl, self.workerId, deviceUUID))
		if r.status_code == 200:
			jobDict = json.loads(r.text)
			return jobDict
		elif r.status_code == 204:
			return None
		else:
			logger.error("ERROR: get_job failed with: %s" % str(r.status_code))
			logger.debug(r.text)
			return False


	def get_job(self, jobId):
		logger.debug("get_job: %s", jobId)
		r = requests.get("%s/jobs/%s" % (self.baseUrl, jobId))
		if r.status_code == 200:
			jobDict = json.loads(r.text)
			return jobDict


	def post_job(self, jobDict):
		logger.debug("post_job: %s", jobDict)
		r = requests.post("%s/jobs" % self.baseUrl, data=jd(jobDict), headers=self.HEADERS)
		if r.status_code == 200:
			return json.loads(r.text)['jobId']
		else:
			logger.warning("Unable to post job: %s" % str(jobDict))
			logger.debug("Response: %s" % r.text)
			return None


	# returns appId
	def post_app(self, appData):
		logger.debug("post_aoo: %s", appData)
		r = requests.post("%s/apps" % self.baseUrl, data=jd(appData), headers=self.HEADERS)
		if r.status_code == 200:
			return json.loads(r.text)['appId']
		else:
			logger.warning("Unable to post app: %s" % str(appData))
			logger.debug("Response: %s" % r.text)
			return None


	def get_app_bundleId(self, bundleId, version=None):
		''' get the appId for given variables
			returns: appId or None if the result is not unique
		'''
		logger.debug("get_app_bundleId: %s", bundleId)
		url = "%s/apps/bundleid/%s" % (self.baseUrl, bundleId)
		if version:
			url += '?version=%s' % version
		r = requests.get(url)
		if r.status_code == 200:
			appsDict = json.loads(r.text)
			if len(appsDict) == 1:
				return appsDict.values()[0]
			logger.debug('%s returned %s results' % (url, len(appsDict)))
		else:
			logger.error('%s request failed: %s %s' % (url, r.status_code, r.text))
		return None


	def get_app_archive(self, appId, archivePath):
		'''	get the ipa file from backend
			returns: True or False
		'''
		logger.debug("get_app_archive: %s", appId)
		r = requests.get("%s/apps/%s/ipa" % (self.baseUrl, appId))
		if r.status_code == 200:
			f = open(archivePath, 'wb')
			f.write(r.content)
			#shutil.copyfileobj(r.raw, f)
			f.close()

			return True
		else:
			logger.warning("Unable to get app archive for app %s" % appId)
			logger.debug("Response: %s" % r.text)
			return False


	def has_app_archive(self, appId):
		logger.debug("has_app_archive: %s", appId)
		logger.debug("%s/apps/%s/ipa" % (self.baseUrl, appId))
		r = requests.head("%s/apps/%s/ipa" % (self.baseUrl, appId))
		if r.status_code == 200:
			return True
		return False


	# returns appId
	def post_app_archive(self, appId, archivePath):
		logger.debug("post_app_archive: %s", appId)
		r = requests.post("%s/apps/%s/ipa" % (self.baseUrl, appId), files={
			'ipa': open(archivePath, 'rb')
		})
		if r.status_code == 200:
			return json.loads(r.text)['appId']
		else:
			logger.warning("Unable to post app archive for app %s" % appId)
			logger.debug("Response: %s" % r.text)
			return None


	# returns runId
	def post_run(self, appId, runState, runId=None, executionStrategy=None):
		logger.debug("post_run: %s", appId)
		data={
			'app': appId,
			'state': runState
		}
		if runId:
			data['_id'] = runId
		if executionStrategy:
			data['executionStrategy'] = executionStrategy
		r = requests.post("%s/runs" % self.baseUrl, data=jd(data), headers=self.HEADERS)
		if r.status_code == 200:
			return json.loads(r.text)['runId']
		else:
			logger.warning("Unable to post run: %s" % str(data))
			logger.debug("Response: %s" % r.text)
			return None


	# returns resultId or None
	def post_result(self, runId, resultType, resultData):
		logger.debug("post_result: %s", runId)
		data = {
			'run': runId,
			'resultInfo': {
				'type': resultType,
				'data': resultData
			}
		}
		r = requests.post("%s/results" % self.baseUrl, headers=self.HEADERS, data=jd(data))
		if r.status_code == 200:
			return json.loads(r.text)['resultId']
		else:
			logger.warning("Unable to post result: %s" % str(data))
			logger.debug("Response: %s" % r.text)
			return None
