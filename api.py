import time
import threading
import json
import sys
import os

__author__ = 'denislavrov'

"""
If you want to port COR-Module to another language, you must implement everything in this file in your target language.
"""


class CORModule:
	def __init__(self, network_adapter=None, *args, **kwargs):
		self.consumes = {}
		self.types = {}
		if network_adapter is None:
			from .comm import CallbackNetworkAdapter
			self.network_adapter = CallbackNetworkAdapter()
		else:
			self.network_adapter = network_adapter
		network_adapter.module = self
		print("Initializaing %s" % type(self).__name__)

	def add_topic(self, type, callback):
		self.consumes[type] = callback

	def register_type(self, type, type_class):
		self.types[type] = type_class

	def messagein(self, message):
		if type(message).__name__ in self.consumes:
			self.consumes[type(message).__name__](message)
		else:
			if "UNSOLICITED" in self.consumes:
				self.consumes["UNSOLICITED"](message)
		if "ANY" in self.consumes:
			self.consumes["ANY"](message)

	def messageout(self, message):
		while self.network_adapter is None:
			time.sleep(0.01)
		self.network_adapter.message_out(message)


class Launcher:
	def __init__(self):
		super().__init__()
		self.module_thread = None
		self.module_instance = None

	def launch_module(self, module_class, *mod_args, **mod_kwargs):
		def mod_loader():
			self.module_instance = module_class(*mod_args, **mod_kwargs)

		self.module_thread = threading.Thread(target=mod_loader)
		self.module_thread.start()

	def wait_for_instance(self):
		while self.module_instance is None:
			time.sleep(0.5)

	def link_internal(self, messagetype, other_loader):
		self.wait_for_instance()
		other_loader.wait_for_instance()
		self.module_instance.network_adapter.register_callback(messagetype, other_loader.module_instance)

	def link_external(self, messagetype, hostport):
		self.wait_for_instance()
		network_adapter = self.module_instance.network_adapter
		if type(network_adapter).__name__ == "TCPSocketNetworkAdapter":
			network_adapter.register_link(messagetype, hostport)
		else:
			print("Can Not Link")


def packaged_import(name):
	components = name.split('.')
	mod = __import__(components[0])
	for comp in components[1:]:
		mod = getattr(mod, comp)
	return mod


def app_loader(loader_id, config_file):
	with open(sys.argv[2], 'r') as appfile:
		appdict = json.load(appfile)

	this_loader = None
	for loader in appdict["Loaders"]:
		if loader["ID"] == loader_id:
			this_loader = loader
			break
	if this_loader is None:
		print("Invalid loader ID")
	modules = this_loader["Modules"]
	launchers = {}
	# loading stage
	for module in modules:
		module_id = module["ID"]
		mod_path = os.path.abspath(module["Path"])
		if mod_path not in sys.path:
			sys.path.append(mod_path)
			print(sys.path)
		module = packaged_import(module_id)
		module_launcher = Launcher()
		launchers[module_id] = module_launcher
		module_launcher.launch_module(module)
	# linking stage
	for module in modules:
		module_id = module["ID"]
		links = module["Links"]
		for link in links:
			module_launcher = launchers[module_id]
			if link["LinkType"] == "Internal":
				for target in link["Targets"]:
					module_launcher.link_internal(link["MessageType"], launchers[target])
	print("App Initialized")

if __name__ == "__main__":
	if len(sys.argv) == 3:
		app_loader(sys.argv[1], sys.argv[2])
	else:
		print("Usage: cor.py loader-id /path/to/app.json")
