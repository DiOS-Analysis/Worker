
class Enum(dict): 
	__getattr__ = dict.get
	def __init__(self, l):
		if isinstance(l,list):
			for e in l:
				self[e.upper()] = e
		elif isinstance(l,dict):
			self.update(l)
