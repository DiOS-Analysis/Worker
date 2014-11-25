#!/usr/bin/env python

import subprocess

#dirty hack to backport check_output to python <2.7
# taken from: http://stackoverflow.com/questions/4814970/subprocess-check-output-doesnt-seem-to-exist-python-2-6-5/13160748#13160748
if "check_output" not in dir( subprocess ): # duck punch it in!
	def f(*popenargs, **kwargs):
		if 'stdout' in kwargs:
			raise ValueError('stdout argument not allowed, it will be overridden.')
		process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
		output, unused_err = process.communicate()
		retcode = process.poll()
		if retcode:
			cmd = kwargs.get("args")
			if cmd is None:
				cmd = popenargs[0]
			raise subprocess.CalledProcessError(retcode, cmd)
		return output
	subprocess.check_output = f


import plistlib
import re
import logging
import os

from store import AppStore
from enum import Enum

import deviceconnection

logger = logging.getLogger('worker.'+__name__)

class iDevice(object):


###### device info stuff

	@staticmethod
	def list_device_ids():
		''' list of the connected devices uuid's
		'''
		output = subprocess.check_output(["idevice_id", "--list"])
		return filter(None, output.split("\n"));

	@classmethod
	def devices(cls):
		''' list of connected devices.
		'''
		return list(iDevice(uuid) for uuid in iDevice.list_device_ids())

	def __init__(self, uuid):
		self.uuid = uuid
		self.deviceDict = {}
		self.accountDict = {}
		self.locale_val = ""


	def __str__(self):
		return "<iDevice: %s>" % self.uuid

	def __repr__(self):
		return "<iDevice: %s>" % self.uuid

	def device_info_dict(self):
		''' raw device information as dict
		'''
		if (len(self.deviceDict) == 0):
			output = subprocess.check_output(["ideviceinfo", "--xml", "--udid", self.uuid])
			self.deviceDict = plistlib.readPlistFromString(output)
		return self.deviceDict

	DEVICE_INFO = Enum(['DeviceName', 'DeviceClass', 'ProductType', 'ProductVersion', 'WiFiAddress'])


	def locale(self):
		''' the devices locale setting
		'''
		if (self.locale_val == ""):
			self.locale_val = subprocess.check_output(["ideviceinfo", "--udid", self.uuid, "--domain", "com.apple.international", "--key", "Locale"]).strip()
		return self.locale_val


	def base_url(self):
		''' the devices base url to access the devices pilot via http tunneled via USB
		'''
		baseUrl = None
		device_handler = deviceconnection.shared_device_handler()
		conn_tuple = device_handler.device_connection_info(self.uuid)
		if conn_tuple:
			baseUrl = "http://%s:%s/" % conn_tuple
		return baseUrl


### more device informations
	def free_bytes(self):
		''' get the free space left on the device in bytes
		'''
		output = subprocess.check_output(["ideviceinfo", "--udid", self.uuid, "--domain", "com.apple.disk_usage", "--key", "TotalDataAvailable"])
		free_bytes = 0
		try:
			free_bytes = long(output)
		except ValueError:
			logger.warning("Unable to get free space for device %s. Output: %s" % (self, output))
		return free_bytes


###### Account stuff
	def account_info_dict(self):
		''' get raw account info from device as dict.
		'''
		if (len(self.accountDict) == 0):
			output = subprocess.check_output(["ideviceinfo", "--xml", "--udid", self.uuid, "--domain", "com.apple.mobile.iTunes.store", "--key", "KnownAccounts"])
			if len(output) > 0:
				self.accountDict = plistlib.readPlistFromString(output)
			else:
				logger.warning("No accounts found for device %s" % device)
				self.accountDict = {}
		return self.accountDict

	ACCOUNT_INFO = Enum({
		'APPLE_ID':'AppleID',
		'UNIQUE_IDENTIFIER':'DSPersonID',
		'STOREFRONT':'AccountStoreFront'
	})


	def accounts(self):
		''' list all known accounts as list of account-dicts
		'''
		accList = self.account_info_dict()
		accounts = []

		for accInfo in accList:
			storeFront = ""
			if self.ACCOUNT_INFO.STOREFRONT in accInfo:
				storeFront = accInfo[self.ACCOUNT_INFO.STOREFRONT].split(",")[0]
				if '-' in storeFront:
					storeFront = storeFront.split('-')[0]
			storeCountry = AppStore.countryForStoreFrontId(storeFront)
			if storeCountry == None or storeCountry == "":
				storeCountry = self.locale().split('_')[-1]
			acc = {
				'uniqueIdentifier': str(accInfo[self.ACCOUNT_INFO.UNIQUE_IDENTIFIER]),
				'appleId': accInfo[self.ACCOUNT_INFO.APPLE_ID],
				'storeCountry': storeCountry.lower()
			}
			accounts.append(acc)
		return accounts


###### App stuff

	APP_INFO = Enum({
		'NAME':'CFBundleName',
		'DISPLAY_NAME':'CFBundleDisplayName',
		'BUNDLE_ID':'CFBundleIdentifier',
		'VERSION':'CFBundleShortVersionString',
		'ACCOUNT_ID':'ApplicationDSID'
	})

	def installed_apps(self):
		''' list all installed apps as dict.
		'''
		output = subprocess.check_output(["ideviceinstaller", "--udid", self.uuid, "--list-apps", "-o", "list_user", "-o", "xml"])
		if (len(output)==0):
			return {}
			
		apps = {}
		plist = []
		try:
			plist = plistlib.readPlistFromString(output)
		except Exception:
			logger.warning("Failed to parse installed apps via xml output. Try to extract data via regex.")
			output = subprocess.check_output(["ideviceinstaller", "--udid", self.uuid, "--list-apps", "-o", "list_user"])
			regex = re.compile("^(?P<bundleId>.*) - (?P<name>.*) (?P<version>(\d+\.*)+)$",re.MULTILINE)
			# r = regex.search(output)
			for i in regex.finditer(output):
				results = i.groupdict()
				data = {
					self.APP_INFO.NAME: results['name'].decode('utf-8').encode("ascii", "ignore"),
					self.APP_INFO.BUNDLE_ID: results['bundleId'],
					self.APP_INFO.VERSION: results['version']
				}
				plist.append(data)
				
		
		for entry in plist:
			appData = {
				'name': '',
				'bundleId': entry[self.APP_INFO.BUNDLE_ID],
				'version': '-2'
			}
			if not self.APP_INFO.DISPLAY_NAME in entry and not self.APP_INFO.NAME in entry:
				logger.warning('Using last part of bundleId as app name! entry:<%s>', entry)
				appData['name'] = appData['bundleId'].split('.')[-1]
			

			if self.APP_INFO.NAME in entry:
				appData['name'] = entry[self.APP_INFO.NAME]
			if self.APP_INFO.DISPLAY_NAME in entry:
				appData['name'] = entry[self.APP_INFO.DISPLAY_NAME]
			if self.APP_INFO.VERSION in entry:
				appData['version'] = entry[self.APP_INFO.VERSION]
			if self.APP_INFO.ACCOUNT_ID in entry:
				appData['accountId'] = entry[self.APP_INFO.ACCOUNT_ID]
			apps[entry[self.APP_INFO.BUNDLE_ID]] = appData

		return apps


	def install(self, app_archive_path):
		''' install an app on the device from given file
			returns True or False
		'''
		result=True
		try:
			output = subprocess.check_output(["ideviceinstaller", "--udid", self.uuid, "--install", app_archive_path])
			logger.debug('output: %s' % output)
			if (len(output)==0):
				result=False
		except subprocess.CalledProcessError as e:
			logger.error('installing app %s failed with: %s <output: %s>' % (app_archive_path, e, output))
			result=False
		return result

	def uninstall(self, bundleId):
		''' uninstall an app on the device from given bundleId
			returns True or False
		'''
		result=True
		try:
			output = subprocess.check_output(["ideviceinstaller", "--udid", self.uuid, "--uninstall", bundleId])
			logger.debug('output: %s' % output)
			if (len(output)==0):
				result=False
		except subprocess.CalledProcessError as e:
			logger.error('uninstalling app %s failed with: %s <output: %s>' % (bundleId, e, output))
			result=False
		return result

	def archive(self, bundleId, app_archive_folder, app_only=True, uninstall=True):
		''' archives an app to `app_archive_folder`
			returns True or False
		'''
		options = ["ideviceinstaller", "--udid", self.uuid, "--archive", bundleId, "-o", "copy="+app_archive_folder, "-o", "remove"]
		if app_only:
			options.extend(["-o", "app_only"])
		if uninstall:
			options.extend(["-o", "uninstall"])

		if not os.path.exists(app_archive_folder):
			os.makedirs(app_archive_folder)
		logger.debug('try archiving app %s with cmd: %s' % (bundleId, ' '.join(options)))
		result=True
		try:
			output = subprocess.check_output(options)
			logger.debug('output: %s' % output)
			if (len(output)==0):
				result=False
		except subprocess.CalledProcessError as e:
			logger.error('archiving app %s failed with: %s <output: %s>', bundleId, e, output)
			result=False
		return result

