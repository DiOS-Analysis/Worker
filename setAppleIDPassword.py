#!/usr/bin/python

import logging
from backend import Backend

logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger('setAppleIDPassword')
logger.setLevel(level=logging.INFO)

def main():
	import argparse

	parser = argparse.ArgumentParser(description='set password for AppleID. CAUTION: Use AppleIDs with payment credentials at you own risk!!! EVERY purchase will be done if possible!!! The password will be stored UNENCRYPTED!!!')
	parser.add_argument('-b','--backend', required=True, help='the backend url')
	parser.add_argument('-a','--appleId', required=True, help='the AppleId')
	parser.add_argument('-p','--password', required=True, help='the password')

	args = parser.parse_args()
	logger.debug(args)

	backend = Backend(args.backend)
	accounts = backend.get_accounts()
	
	passwordUpdated = False
	for accId, acc in accounts.items():
		if 'appleId' in acc and acc['appleId'] == args.appleId:
			logger.debug(str(acc))
			acc['password'] = args.password
			passwordUpdated = backend.post_account(acc)
			break
	
	if passwordUpdated:
		print "password updated for AppleId '%s'" % args.appleId
	else:
		print "unable to update password for AppleId '%s'" % args.appleId


if __name__ == '__main__':
	main()
