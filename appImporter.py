#!/usr/bin/python

import argparse
import sys
import os
import shutil
import tempfile
import biplist
# most plists reads will fail by using just plistlib

import logging
logging.basicConfig(level=logging.DEBUG)

import zipfile

from backend import Backend

METADATA_FILENAME='iTunesMetadata.plist'
METADATA_KV_MAP = {
	'bundleId':'softwareVersionBundleId',
	'version':'bundleShortVersionString',
	'name':'itemName',
	'trackId':'itemId',
	'artworkUrl60':'softwareIcon57x57URL',
	'artistName':'artistName',
	'primaryGenreName':'genre',
	'releaseDate':'releaseDate'
}
# + type + accountId


def is_present_at_backend(backend, appData):
	version = None
	if 'version' in appData:
		version = appData['version']
	if backend.get_app_bundleId(appData['bundleId'], version=version):
		return True
	return False


def add_app_to_backend(backend, appData, ipaFilename):
	# required: 'bundleId', 'version', 'type', 'name', 'trackId', 'account'
	appId = backend.post_app(appData)
	if appId:
		logging.debug('appInfo for %s succesfully added <%s>', appData['bundleId'], appId)
		if backend.post_app_archive(appId, ipaFilename):
			logging.info('%s succesfully added <%s>', appData['bundleId'], appId)
		else:
			logging.error('post appArchive for %s failed <%s>', appData['bundleId'], appId)
	else:
		logging.error('post appInfo for %s failed <%s>', appData['bundleId'], appId)
	return appId


def accountId_from_appleId(backend, appleId):
	accounts = backend.get_accounts()
	for acc,accDict in accounts.iteritems():
		if accDict['appleId'] == appleId:
			return accDict['uniqueIdentifier']

#
# setip argparser

parser = argparse.ArgumentParser(description='Search for apps within the given folder and add it to the backend.')
parser.add_argument('-a','--app-folder', default='~/Music/iTunes/iTunes Media/Mobile Applications/', help='The folder containing the apps to import.')
parser.add_argument('-b','--backend', required=True, help='the backend url.')

args = parser.parse_args()
logging.debug(args)


# setup

backend = Backend(args.backend)
path = os.path.expanduser(unicode(args.app_folder))

if not os.path.exists(path):
	logging.error('Path not found: %s', path)
	sys.exit(1)

for filename in os.listdir(path):
	logging.info('processing %s', filename)
	filepath = "%s/%s" % (path, filename)
	if not zipfile.is_zipfile(filepath):
		logging.warning('%s is not a zipfile! - skipping', filename)
		continue

	appData = {
		'type':'AppStoreApp'
	}
	with zipfile.ZipFile(filepath, 'r') as appachive:
		if not METADATA_FILENAME in appachive.namelist():
			logging.warning('%s has no %s file' % (filename, METADATA_FILENAME))
			continue
		metadatafile = appachive.open(METADATA_FILENAME)

		# create a copy of the metadatafile
		## biplist needs seek() - which requieres a real file
		f = tempfile.TemporaryFile()
		shutil.copyfileobj(metadatafile, f)
		#
		metadatafile.close()
		plist = {}
		try:
			plist = biplist.readPlist(f)
		except (biplist.InvalidPlistException, biplist.NotBinaryPlistException), e:
			print "Not a plist:", e
			logging.error('Reading plist failed for %s - skipping', filename)
			continue
		finally:
			f.close()

		for k,v in METADATA_KV_MAP.iteritems():
			if v in plist:
				appData[k] = plist[v]

		# read old account format too
		if 'appleId' in plist:
			appData['account'] = accountId_from_appleId(backend, plist['appleId'])
		else:
			if 'com.apple.iTunesStore.downloadInfo' in plist:
				dlInfo = plist['com.apple.iTunesStore.downloadInfo']
				if 'accountInfo' in dlInfo:
					accInfo = dlInfo['accountInfo']
					if 'DSPersonID' in accInfo:
						appData['account'] = accInfo['DSPersonID']

		# check verison
		if not 'version' in appData and 'bundleVersion' in plist:
			appData['version'] = plist['bundleVersion']
		if not 'version' in appData and 'releaseDate' in plist:
			appData['version'] = plist['releaseDate']


	# add if not already present
	if not is_present_at_backend(backend, appData):
		logging.info('aading app to backend: %s', appData['bundleId'])
		if add_app_to_backend(backend, appData, filepath):
			print '\n### DONE: %s\n' % appData['bundleId']
		else:
			print '\n### FAILED: %s\n' % appData['bundleId']

	