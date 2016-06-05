__author__ = 'denis'
import socket, threading, struct, time
from .protocol.message_pb2 import CORMessage

"""
If you want to port COR-Module to another language, you must implement everything in this file in your target language.
"""


class NetworkAdapter:

	def message_out(self, message):
		message_type = type(message).__name__
		cormsg = CORMessage()
		cormsg.type = message_type
		cormsg.data = message.SerializeToString()
		if message_type in self.routes:
			sock = self.endpoints[self.routes[message_type]]
			cordata = cormsg.SerializeToString()
			corlength = struct.pack(">I", len(cordata))
			try:
				sock.send(corlength+cordata)
			except Exception:
				print("Unable to send message, attempting to reconnect")
				self._connect(self.routes[message_type])
				self.message_out(message)
		else:
			print("Route not found")
			pass

	# COR 5.0, direct message extension
	def direct_message(self, message, url):
		pass

	def _connect(self, hostport):
		aparts = hostport.split(":")
		if hostport in self.endpoints:
			self.endpoints[hostport].close()
		while True: 
			try:
				sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				sock.connect((aparts[0], int(aparts[1])))
				if self.nodelay:
					# Disables Nagle's Algorithm to reduce latency
					sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
				self.endpoints[hostport] = sock
				print("Connected to " + hostport)
				break
			except Exception as e:
				print(e)
				print("Connection to %s failed retrying" % hostport)
				time.sleep(1)

	def register_link(self, atype, hostport):
		if hostport not in self.endpoints:
			self._connect(hostport)
		self.routes[atype] = hostport

	def server_thread(self):
		self.server_socket.listen(10)
		while True:
			conn, addr = self.server_socket.accept()
			clientt = threading.Thread(target=self.client_thread, args=(conn,))
			clientt.start()

	def client_thread(self, conn):
		while True:
			lenbuf = conn.recv(4)
			if not lenbuf:
				time.sleep(0.0001)
				continue
			msglen = struct.unpack(">I", lenbuf)[0]
			fullmessage = b""
			while len(fullmessage) < msglen:
				rcv_buf_size = 8192 if (msglen - len(fullmessage)) > 8192 else (msglen - len(fullmessage))
				fullmessage += conn.recv(rcv_buf_size)
			cormsg = CORMessage()
			try:
				cormsg.ParseFromString(fullmessage)
				print("Received: " + cormsg.type)
			except Exception:
				print("Received a corrupt message, reseting connection")
				conn.close()
				return
			# type parse
			if cormsg.type in self.module.types:
				msg_instance = self.module.types[cormsg.type]()
				msg_instance.ParseFromString(cormsg.data)
				self.module.messagein(msg_instance)
			else:
				print("Type " + cormsg.type + " is not declared to be received")

	def __init__(self, module, local_socket="", bind_url="127.0.0.1:6090", nodelay=True):
		super().__init__()
		self.nodelay = nodelay
		self.endpoints = {}
		self.module = module
		self.routes = {}
		self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# allow to reuse the address (in case of server crash and quick restart)
		self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		aparts = bind_url.split(":")
		self.server_socket.bind((aparts[0], int(aparts[1])))
		self.sthread = threading.Thread(target=self.server_thread)
		self.sthread.start()

