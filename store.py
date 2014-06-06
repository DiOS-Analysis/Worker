from bs4 import BeautifulSoup
import urllib2
import json

class AppStoreException(Exception):
	pass
	

class AppStore(object):
	
	storeFrontIdToCountryDict = {
		'143563':'DZ','143564':'AO','143538':'AI','143540':'AG','143505':'AR','143524':'AM','143460':'AU','143445':'AT','143568':'AZ','143559':'BH','143490':'BD','143541':'BB','143565':'BY','143446':'BE','143555':'BZ','143542':'BM','143556':'BO','143525':'BW','143503':'BR','143543':'VG','143560':'BN','143526':'BG','143455':'CA','143544':'KY','143483':'CL','143465':'CN','143501':'CO','143495':'CR','143527':'CI','143494':'HR','143557':'CY','143489':'CZ','143458':'DK','143545':'DM','143508':'DO','143509':'EC','143516':'EG','143506':'SV','143518':'EE','143447':'FI','143442':'FR','143443':'DE','143573':'GH','143448':'GR','143546':'GD','143504':'GT','143553':'GY','143510':'HN','143463':'HK','143482':'HU','143558':'IS','143467':'IN','143476':'ID','143449':'IE','143491':'IL','143450':'IT','143511':'JM','143462':'JP','143528':'JO','143517':'KZ','143529':'KE','143466':'KR','143493':'KW','143519':'LV','143497':'LB','143522':'LI','143520':'LT','143451':'LU','143515':'MO','143530':'MK','143531':'MG','143473':'MY','143488':'MV','143532':'ML','143521':'MT','143533':'MU','143468':'MX','143523':'MD','143547':'MS','143484':'NP','143452':'NL','143461':'NZ','143512':'NI','143534':'NE','143561':'NG','143457':'NO','143562':'OM','143477':'PK','143485':'PA','143513':'PY','143507':'PE','143474':'PH','143478':'PL','143453':'PT','143498':'QA','143487':'RO','143469':'RU','143479':'SA','143535':'SN','143500':'RS','143464':'SG','143496':'SK','143499':'SI','143472':'ZA','143454':'ES','143486':'LK','143548':'KN','143549':'LC','143550':'VC','143554':'SR','143456':'SE','143459':'CH','143470':'TW','143572':'TZ','143475':'TH','143539':'BS','143551':'TT','143536':'TN','143480':'TR','143552':'TC','143537':'UG','143444':'GB','143492':'UA','143481':'AE','143514':'UY','143441':'US','143566':'UZ','143502':'VE','143471':'VN','143571':'YE'
	}
	

	view_SW_URL = "https://itunes.apple.com/%(country)s/app/id%(trackId)d"
	search_Bundle_URL = "https://itunes.apple.com/%(country)s/lookup?bundleId=%(bundleId)s"
	lookup_URL = "https://itunes.apple.com/lookup?id=%(trackId)d&country=%(country)s"

	def __do_request(self, url):
		
		request = urllib2.Request(url)
		request.add_header('User-Agent', 'iTunes-iPhone/5.1.1 (3)')
		response = None
		try:
			response = urllib2.urlopen(request, timeout=15)
		except urllib2.URLError:
			response = urllib2.urlopen(request, timeout=15)
				
		if response.code != 200:
			raise AppStoreException("Request failed: %d" % response.code)
		return response
		

	def __init__(self, country="de"):
		self.country = country
	
	
	def get_app_info(self, appId):
		''' Get the appInfo from the iTunes store. 
			The returned dictionary contains all neccessary fields needed to purchase the app.
		'''
		url = AppStore.view_SW_URL % {"country":self.country, "trackId":appId}

		data = ""
		try:
			response = self.__do_request(url)
			data = response.read()
		except urllib2.URLError as e:
			raise AppStoreException(e)

		soup = BeautifulSoup(data)
		buyDivs = soup.find_all(class_="buy")
		if (len(buyDivs) > 0):
			return buyDivs[0].attrs
		else:
			raise AppStoreException("No App info found")


	def get_app_data(self, appId):
		''' Returns all data available from the store via lookup for the given appId (trackId)
		'''
		url = AppStore.lookup_URL % {"country":self.country, "trackId":appId}
		
		data = {}
		try:
			response = self.__do_request(url)
			data = json.loads(response.read())
		except urllib2.URLError as e:
			raise AppStoreException(e)
		
		if 'resultCount' in data:
			count = data['resultCount']
			if  count < 1:
				raise AppStoreException("BundleId not found")
			elif count > 1 :
				raise AppStoreException("BundleId not unique")
			else:
				return data['results'][0]
		else:
			raise AppStoreException("Invalid response data")	



	def get_trackId_for_bundleId(self, bundleId):
		''' Returns the corresponding trackId to the given bundle identifier.
			This function will throw an AppStoreException unless exacly one result is found.
		'''
		url = AppStore.search_Bundle_URL % {"country":self.country, "bundleId":bundleId}

		data = {}
		try:
			response = self.__do_request(url)
			data = json.loads(response.read())
		except urllib2.URLError as e:
			raise AppStoreException(e)
		
		if 'resultCount' in data:
			count = data['resultCount']
			if  count < 1:
				raise AppStoreException("bundleId not found")
			elif count > 1 :
				raise AppStoreException("bundleId not unique")
			else:
				return data['results'][0]['trackId']
		else:
			raise AppStoreException("Invalid response data")	
		
		
	@staticmethod
	def countryForStoreFrontId(storeFrontId):
		if storeFrontId in AppStore.storeFrontIdToCountryDict:
			return AppStore.storeFrontIdToCountryDict[storeFrontId]
		else:
			return None