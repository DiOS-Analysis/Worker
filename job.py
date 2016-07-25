
import os
import logging
import base64
import time

from enum import Enum
from store import AppStore, AppStoreException
from pilot import Pilot

logger = logging.getLogger('worker.'+__name__)

class JobExecutionError(Exception):
	pass


class Job(object):

	STATE = Enum([u'undefined', u'pending', u'running', u'finished', u'failed'])
	TYPE = Enum([u'run_app', u'install_app', u'exec_cmd'])

	def __init__(self, backend, device, jobDict):
		self.jobDict = jobDict
		if not '_id' in jobDict:
			raise JobExecutionError('No jobId present')
		self.jobId = jobDict['_id']

		self.device = device
		self.backend = backend

	def execute(self):
		raise NotImplementedError



class InstallAppJob(Job):

	APP_ARCHIVE_PATH='/tmp/apparchive/'

	def __init__(self, backend, device, jobDict):
		super(InstallAppJob, self).__init__(backend, device, jobDict)
		self.appId = None

	def _archive_app_binary(self, bundleId):
		logger.debug('archiving %s' % bundleId)
		try:
			### add app binary to backend
			self.device.archive(bundleId, self.APP_ARCHIVE_PATH, app_only=True)
			appPath = '%s%s.ipa' % (self.APP_ARCHIVE_PATH, bundleId)
			logger.debug('archiving app %s to %s' % (bundleId, appPath))
			self.backend.post_app_archive(self.appId, appPath)
			os.remove(appPath) 		#delete app from disk
		except Exception, e:
			raise JobExecutionError('unable to archive app binary: %s' % str(e))


	def _install_app(self, pilot):
		''' try to install the app
			will raise a JobExecutionError on failure

			returns:
				True if the app was just installed
				False if the app was already installed before

		'''
		logger.debug('_install_app')

		if not 'jobInfo' in self.jobDict:
			raise JobExecutionError('no jobInfo given')
		jobInfo = self.jobDict['jobInfo']

		if not 'appType' in jobInfo:
			raise JobExecutionError('no app type given')

		if not 'bundleId' in jobInfo:
			raise JobExecutionError('no bundleId given')
		bundleId = jobInfo['bundleId']

		version = None
		if 'version' in jobInfo:
			version = jobInfo['version']

		#check app type
		if 'AppStoreApp' == jobInfo['appType']:
			logger.debug('installing appstore app %s' % bundleId)

			# use device data due to better version data
			installedApps = self.device.installed_apps()

			# check if app already installed
			alreadyInstalled = False
			if bundleId in installedApps:
				logger.debug('app %s is already installed' % bundleId)
				# check for matching version number
				if version:
					installedVersion = installedApps[bundleId]['version']
					if version != installedVersion:
						raise JobExecutionError('wrong app version installed!')
				# the app is already installed and versions are compatible
				alreadyInstalled = True

			# check the backend for already existing app
			app = self.backend.get_app_bundleId(bundleId, version)
			logger.debug('backend result for bundleId %s: %s' % (bundleId, app))
			if app and '_id' in app:
				self.appId = app['_id']

			# case 1: already installed and registered with backend
			if self.appId and alreadyInstalled:
				# app is installed and registred with backend
				logger.info('App is already installed and registred with backend <%s>' % self.appId)
				return False

			# case 2: install from backend
			elif self.appId:
				# install from backend
				
				# dirty check for ipa-size < ~50MB
				if app and 'fileSizeBytes' in app:
					size = 0
					try:
						size = int(app['fileSizeBytes'])
					except ValueError:
						size = -1
					if size > 0 or size < 40000000:
						
						# actually install from backend
						logger.info('installing app %s from backend (size: %s)' % (bundleId,size))
						if not os.path.exists(self.APP_ARCHIVE_PATH):
							os.makedirs(self.APP_ARCHIVE_PATH)
						appPath = '%s%s.ipa' % (self.APP_ARCHIVE_PATH, bundleId)
						
						logger.debug('fetch app %s from backend' % bundleId)
						if self.backend.get_app_archive(self.appId, appPath):							
							logger.info('installing app %s via device handler' % bundleId)
							self.device.install(appPath)
							os.remove(appPath)
							tries = 3
							while tries > 0 and bundleId not in self.device.installed_apps():
								tries = tries-1
								time.sleep(60)
							if bundleId in self.device.installed_apps():
								return True
							else:							
								logging.warning('installing the app via device handler failed! - Install via AppStore instead')
						else:
							logger.warning('unable to get app archive from backend. appId: <%s>' % self.appId)	
					else:
						logger.info('skipping install from backend to avoid ideviceinstaller error (ipa to large)')						
				else:
					logger.info('skipping install from backend to avoid ideviceinstaller error (unknown ipa size)')
					
			# case 3: install from appstore
			# case 4: installed but unregistred

			storeCountry = 'de'
			if 'storeCountry' in jobInfo:
				storeCountry = jobInfo['storeCountry']

			## get appInfo
			logger.debug('fetch appInfo from iTunesStore')
			store = AppStore(storeCountry)
			trackId = 0
			appInfo = {}
			try:
				trackId = store.get_trackId_for_bundleId(bundleId)
				appInfo = store.get_app_info(trackId)
			except AppStoreException as e:
				logger.error('unable to get appInfo: %s ', e)
				raise JobExecutionError('unable to get appInfo: AppStoreException')
			
			self.jobDict['appInfo'] = appInfo
			logger.debug('using appInfo: %s' % str(appInfo))


			## get account
			accountId = ''
			if alreadyInstalled:
				# get account info from device
				installedAppInfo = self.device.installed_apps()[bundleId]
				if 'accountId' in installedAppInfo:
					accountId = installedAppInfo['accountId']
			else:
				if 'accountId' in jobInfo:
					accountId = jobInfo['accountId']
				else:
					for acc in self.device.accounts():
						if acc['storeCountry'] == storeCountry:
							accountId = acc['uniqueIdentifier']

			if accountId == '':
				raise JobExecutionError('unable to find a valid account identifier')

			logger.debug('using account %s' % accountId)

			# case 3 only
			if not alreadyInstalled:
				# install via appstore
				logger.info('installing app %s via appstore' % bundleId)

				if not pilot.install_appstore(appInfo, accountId, taskInfo={'backendUrl':self.backend.baseUrl}):
					logger.error("App installation failed")
					raise JobExecutionError("App installation failed")

			## add app to backend
			### the app data is currently taken from ideviceinstaller (via device.installed_apps)
			### alternatively the pilot could be used to access the /applications rest api
			appData = store.get_app_data(trackId)
			appData['account'] = accountId
			appData['name'] = appData['trackName']
			self.appId = self.backend.post_app(appData)

			# end install via appstore
			return not alreadyInstalled

		elif 'CydiaApp' == jobInfo['appType']:
			logger.info('installing app %s via cydia' % bundleId)
			pilot.install_cydia(bundleId)
			return True

		else:
			raise JobExecutionError('invalid app type')


	def execute(self):
	
		logger.info("executing InstallAppJob %s on device %s" % (self.jobId, self.device))
	
		# allow InstallAppJobs to exist/run without a corresponding backendJob
		backendJobData = {}
		if self.jobId:
			backendJobData = self.backend.get_job(self.jobId)
			## set job running
			backendJobData['state'] = Job.STATE.RUNNING
			self.backend.post_job(backendJobData)
	
		pilot = Pilot(self.device.base_url())
	
		result = True
		try:
			self.appJustInstalled = self._install_app(pilot)
			if not self.appId:
				raise JobExecutionError("No appId present")
	
			jobInfo = self.jobDict['jobInfo']
			bundleId = jobInfo['bundleId']
	
			if self.device.ios_version()[0] > 8:
				logger.debug("skipping app archiving since device is running iOS 9 or later")
			else:
				logger.debug("check if backend already has an app ipa")
				if not self.backend.has_app_archive(self.appId):
					self._archive_app_binary(bundleId)
			
			backendJobData['state'] = Job.STATE.FINISHED
	
		except JobExecutionError, e:
			logger.error("Job execution failed: %s" % str(e))
			backendJobData['state'] = Job.STATE.FAILED
			result = False
	
		## set job finished
		if self.jobId:
			self.backend.post_job(backendJobData)
	
		return result
	


class RunAppJob(Job):

	APP_ARCHIVE_PATH='/tmp/apparchive/'

	def __init__(self, backend, device, jobDict):
		super(RunAppJob, self).__init__(backend, device, jobDict)
		self.appId = None


	def _install_app(self, pilot):
		''' try to install the app
			returns:
				True if the app was just installed
				False if the app was already installed before

		'''
		logger.debug('_installApp')
		installJobDict = {
			'_id': False,
			'jobInfo': self.jobDict['jobInfo']
		}
		installJob = InstallAppJob(self.backend, self.device, installJobDict)
		logger.debug('executing InstallJob')
		if not installJob.execute():
			logger.debug('Unable to install app')
			raise JobExecutionError('Unable to install app')

		logger.debug('app is installed now')
		self.appId = installJob.appId
		return installJob.appJustInstalled
	

	def _archive_app_binary(self, bundleId):
		logger.debug('archiving %s' % bundleId)
		try:
			### add app binary to backend
			self.device.archive(bundleId, self.APP_ARCHIVE_PATH, app_only=True)
			appPath = '%s%s.ipa' % (self.APP_ARCHIVE_PATH, bundleId)
			logger.debug('archiving app %s to %s' % (bundleId, appPath))
			self.backend.post_app_archive(self.appId, appPath)
			os.remove(appPath) 		#delete app from disk
		except Exception, e:
			raise JobExecutionError('unable to archive app binary: %s' % str(e))


	def _execute_app(self, pilot, bundleId, runId, executionStrategy=None):
		''' execute the app '''
		logger.debug('_execute_app')
		taskInfo = {
			'runId':runId,
			'backendUrl':self.backend.baseUrl,
		}
		if executionStrategy:
			taskInfo['executionStrategy'] = executionStrategy
		pilot.run_auto_execution(bundleId, taskInfo=taskInfo)


	def _save_run_results(self, runId, bundleId, uninstallApp=True):
		logger.info("Saving apparchive to backend")
		if self.device.archive(bundleId, self.APP_ARCHIVE_PATH, app_only=False):
			appPath = self.APP_ARCHIVE_PATH + bundleId + '.ipa'
			if os.path.exists(appPath):
				f = open(appPath, 'rb')
				appData = f.read()
				f.close()
				try:
					appData = base64.b64encode(appData)
					self.backend.post_result(runId, 'app_archive', appData)
				except TypeError:
					logger.error('Unable to encode app archive!')

				#delete app archive from disk
				os.remove(appPath)
		
		if uninstallApp:
			self.device.uninstall(bundleId)



	def execute(self):

		logger.info("executing RunAppJob %s on device %s" % (self.jobId, self.device))

		backendJobData = self.backend.get_job(self.jobId)
		## set job running
		backendJobData['state'] = Job.STATE.RUNNING
		self.backend.post_job(backendJobData)

		pilot = Pilot(self.device.base_url())

		try:
			installDone = self._install_app(pilot)
			if not self.appId:
				raise JobExecutionError("No appId present")

			jobInfo = self.jobDict['jobInfo']
			bundleId = jobInfo['bundleId']

			if self.device.ios_version()[0] > 8:
				logger.debug("skipping app archiving since device is running iOS 9 or later")
			else:
				if not self.backend.has_app_archive(self.appId):
					self._archive_app_binary(bundleId)

			executionStrategy = None
			if 'executionStrategy' in jobInfo:
				executionStrategy = jobInfo['executionStrategy']
				
			logger.debug('post_run')
			## add run to backend
			runId = self.backend.post_run(self.appId, self.backend.RUN_STATE.RUNNING)
			
			logger.info('starting app pilot execution')
			self._execute_app(pilot, bundleId, runId, executionStrategy)

			if installDone:
				logger.info("uninstalling app (%s)" % bundleId)
				self.device.uninstall(bundleId)
			# # save the results and install the app if not previously installed
			# self._save_run_results(runId, bundleId, uninstallApp=installDone)

			## set run finished
			self.backend.post_run(self.appId, self.backend.RUN_STATE.FINISHED, runId=runId, executionStrategy=executionStrategy)

		except JobExecutionError, e:
			logger.error("Job execution failed: %s" % str(e))
			backendJobData['state'] = Job.STATE.FAILED
			self.backend.post_job(backendJobData)
			return False

		## set job finished
		backendJobData['state'] = Job.STATE.FINISHED
		self.backend.post_job(backendJobData)

		return True


class ExecuteCmdJob(Job):

	def __init__(self, backend, device, jobDict):
		super(ExecuteCmdJob, self).__init__(backend, device, jobDict)

		if 'process' in jobDict:
			self.process = jobDict['process']
		if 'command' in jobDict:
			self.command = jobDict['command']

	def execute(self):
		if self.process and self.execute:
			pilot = Pilot(self.device.base_url())
			pilot.inject(self.process, self.command)
		else:
			raise JobExecutionError("Process or command missing")


class JobFactory(object):

	@classmethod
	def job_from_dict(cls, jobDict, backend, device):
		job = None
		if 'type' in jobDict:
			jobType = jobDict['type']
			if jobType == Job.TYPE.RUN_APP:
				job = RunAppJob(backend, device, jobDict)
			elif jobType == Job.TYPE.INSTALL_APP:
				job = InstallAppJob(backend, device, jobDict)
			elif jobType == Job.TYPE.EXEC_CMD:
				job = ExecuteCmdJob(backend, device, jobDict)
		else:
			logger.error('jobDict does not contain a type!')
		if job:
			logger.info('job created: %s' % str(job))
		return job


