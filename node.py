import time
from collections import deque
from binascii import hexlify

import node_config as config
from packet import *

try:
    import logging as log
except:
    import ulogging as log

# util: unsigned increment
def uincr(x, y=1):
    return (x+y)%4294967296
# util: unsigned decrement
def udecr(x, y=1):
    if r < 0: return x-y+4294967296
    else: return x-y
# util: address must be exactly 8 bytes
def conform_address(addr):
    if not isinstance(addr, bytes):
        #TODO try catch
        addr = bytes(addr, 'ascii')
    l = len(addr)
    if l == 8: return addr
    # if too big use bottom 8 bytes
    elif l > 8:
        return addr[l-8:]
    # if too small add extra bytes
    else:
        return b'\xff'*(8-l) + addr

# simple timeout base class
class Expirable:
    def __repr__(self):
        return '<'+','.join(f"{k}={v}" for k, v in self.__dict__.items())+'>'
    def __init__(self, lifetime):
        self.timestamp = time.time()
        self.lifetime = lifetime
        self.alive = True
    def update(self):
        if time.time() >= self.timestamp + self.lifetime:
            self.alive = False
    def reset(self, lifetime:int=None):
        if not isinstance(lifetime, int): raise ValueError
        if lifetime:
            self.lifetime = lifetime
        self.timestamp = time.time()


# outbox data waiting for valid route
class QueuedData(Expirable):
    def __init__(self, dest_addr, data):
        super().__init__(config.DATA_QUEUE_TIMEOUT)
        self.dest_addr = dest_addr
        self.data = data


# expirable rreq structure
# for blacklisting nodes exhibiting strange behavior
class RecentRREQ(Expirable):
    def __eq__(self, other):
        if hasattr(other, 'dest_addr') and hasattr(other, 'orig_seq'):
            return self.dest_addr == other.dest_addr and self.orig_seq == other.orig_seq
        else:
            return False
    def __init__(self, rreq):
        super().__init__(lifetime=config.PATH_DISCOVERY_TIME)
        self.orig_seq = rreq.orig_seq
        self.dest_addr = rreq.dest_addr

# considered "valid" if seq_num and next hop fields not empty, AND timer not expired
# always initialized with ACTIVE_ROUTE_TIMEOUT
class Route(Expirable):
    def __init__(self, next_hop:bytes, seq_num:int, hops:int, seq_valid:bool, lifetime:int):
        super().__init__(lifetime=lifetime)
        self.next_hop = next_hop
        self.seq_num = seq_num
        self.hops = hops
        self.seq_valid = seq_valid
    def valid(self):
        v = self.next_hop != b''
        v &= self.seq_valid
        return v and self.alive

# aka "precursors"
# track all adjacent nodes, use for next hop unicast if 
class Neighbor(Expirable):
    def __init__(self, rssi:int=0, snr:int=0, retries=config.NEIGHBOR_MAX_REPAIRS):
        super().__init__(config.ACTIVE_ROUTE_TIMEOUT)
        self.rssi = rssi
        self.snr = snr
        self.retries = retries

# routing table structure
class RoutingTable:
    def __repr__(self):
        a = f'{"ADDR":<9}{"NEXT":<9}{"SEQ":<8}{"HOPS":<5}{"LIFETIME"}'
        for k,v in self.table.items():
            a += f'\n{k} {v.next_hop}{v.seq_num:<8}{v.hops:<5}{v.lifetime:<5}'
        return a
    def __getitem__(self, key:bytes):
        if key in self.table.keys():
                return self.table[key]
        return None
    def __init__(self):
        self.table = {}
    def update(self):
        for route in self.table.values():
            route.update()
    def add_update(self, addr:bytes, next_hop:bytes=b'', seq_num=0, hops=0, seq_valid=0, lifetime=config.ACTIVE_ROUTE_TIMEOUT):
        old = self.table.get(addr)
        if old:
            if ((seq_num - old.seq_num > 0) or
                (seq_num == old.seq_num and hops < old.hops) or
                (not old.valid())):
                pass
            else:
                return False
        self.table[addr] = Route(next_hop=next_hop, seq_num=seq_num, hops=hops, seq_valid=seq_valid, lifetime=lifetime)
        return True

class Node:
    def __repr__(self):
        out = f'NODE:{self.addr}\nSEQ:{self.seq_num},RREQID:{self.rreq_id},'
        out += f'INBOX:{len(self.rx_fifo)},OUTBOX:{len(self.tx_fifo)}\n'
        out += ' == ROUTES == \n'
        out += self.routing_table.__repr__()
        out += '\n == RECENTS == \n'
        out += '\n'.join(f" > {k}:{v}" for k, v in self.recent_rreqs.items())
        return out
    
    def __init__(self, node_addr:bytes, nickname:str=''):

        self.addr = conform_address(node_addr)
        self.nickname = nickname

        self.seq_num = 0
        self.rreq_id = 0

        # store known routes. { 8-byte addr : Route() }
        self.routing_table = RoutingTable()

        # aka precursors. handle rerrs etc
        self.neighbors = {}

        # store recent received rreqs {orig_addr : {dest_addr : orig_seq}}
        self.recent_rreqs = {}

        # blacklist nodes exhibiting strange/malicious behavior
        self.blacklist = []

        # packet mailboxes
        self.rx_fifo = deque((), config.PACKET_INBOX_SZ)
        self.tx_fifo = deque((), config.PACKET_OUTBOX_SZ)

        # queued outgoing messages
        self.queued = []

    
    # return nickname if exists, else addr string
    def whoami(self) -> str:
        if self.nickname:
            return self.nickname
        else:
            return hexlify(self.addr).decode('ascii')
    
    # log wrapper to show nickname
    def log(self, msg):
        log.debug(f'{self.whoami()}:{msg}')
    
    # MAIN RECV CALLBACK. if valid, packetize, add to inbox
    # all routing stuff handled internally
    # incoming datagrams will show up in data inbox
    def on_recv(self, raw:bytes, rssi=0, snr=0):
        try:
            p = Packet(raw, rssi, snr)
            self.rx_fifo.append(p)
            self.log(f'recv packet: {p.send_addr}')
        except PacketBadCrcError:
            self.log(f'recv bad checksum, ignoring packet')
        except PacketBadLenError:
            self.log(f'recv bad len, ignoring packet')
    
    # MAIN UPDATE FUNCTION, call at regular interval
    # updates all internal states, handles inbox/outbox
    # returns next outgoing packet if exists
    def update(self):

        # update, repair or purge neighbors
        rm = []
        for k in self.neighbors.keys():
            self.neighbors[k].update()
            if not self.neighbors[k].alive:
                if self.neighbors[k].retries:
                    self._send_hello(k)
                else:
                    self.log(f'expire neighbor: {k}')
                    rm.append(k)
        for k in rm:
            del self.neighbors[k]

        # 6.5: count down, purge recent rreqs that have expired
        rm = []
        for orig in self.recent_rreqs.keys():
            for dest in self.recent_rreqs[orig].keys():
                self.recent_rreqs[orig][dest].update()
                if not self.recent_rreqs[orig][dest].alive:
                    rm.append([orig, dest])
        for i in rm:
            self.log(f'expired rreq: {i[0]}>>>{i[1]}')
            del self.recent_rreqs[i[0]][i[1]]

        # count down route lifetimes
        self.routing_table.update()
        
        # update blacklist
        rm = []
        for i,addr in enumerate(self.blacklist):
            if len(self.recent_rreqs[i]) < config.MAX_RECENT_RREQS:
                rm.append(addr)
        for i in rm:
            self.log(f'unblacklisting: {i}')
            self.blacklist.remove(i)
        
        # update queued data
        for i,d in enumerate(self.queued):
            route = self.routing_table[d.dest_addr]
            if route and route.valid():
                self.log(f'found route for queued: {d}')
                dd = self.queued.pop(i)
                self._send_data(dd.dest_addr, dd.data)
            else:
                self.queued[i].update()
                if not self.queued[i].alive:
                    self.log(f'expired queued data: {d}')
                    self.queued.pop(i)


        # process next packet in inbox
        self._process_rx()

        # process next packet in outbox
        # return raw bytes to be passed to encryption, radio, etc
        if len(self.tx_fifo):
            return self.tx_fifo.popleft()
        return None

    # MAIN SEND FUNCTION, sends datagram(s)
    # user should only ever use this to send stuff
    # protocol should handle all route maintenance etc
    def send(self, dest_addr:bytes, data:str):
        route = self.routing_table[dest_addr]

        # If route exists, send data
        if route and route.valid():
            self._send_data(dest_addr, data)
        else:
            # No valid route, initiate route discovery (RREQ)
            self._send_rreq(dest_addr)
            # Optionally, queue the data until a route is established
            self.queued.append(QueuedData(dest_addr, data))
        
    # only called when valid route exists
    # push packets into the tx fifo
    def _send_data(self, dest_addr:bytes, data:str):
        
        # unicast address, aka next hop, aka recv
        recv_addr = self.routing_table[dest_addr].next_hop
        d = DATAGRAM()
        # data fits in single packet
        if len(data) <= PAYLOAD_MAX_LEN:
            d.set_data(dest_addr=dest_addr, orig_addr=self.addr, orig_seq=self.seq_num, data=data)
            self.tx_fifo.append(Packet().construct(AODVType.DATA, self.addr, recv_addr, d.pack(), 255))
        # data too big for one packet
        else:
            i = 0
            while i < len(data):
                d.set_data(dest_addr=dest_addr, orig_addr=self.addr, orig_seq=self.seq_num, data=data[i:i+PAYLOAD_MAX_LEN])
                self.tx_fifo.append(Packet().construct(AODVType.DATA, self.addr, recv_addr, d.pack(), 255))
                i += PAYLOAD_MAX_LEN

    # process inbox
    def _process_rx(self):
        # exit if inbox empty
        if not len(self.rx_fifo):
            # self.log(f'inbox empty')
            return
        
        # pop the packet
        p = self.rx_fifo.popleft()

        # INCREMENT INCOMING HOPS !!!
        # (invalidates checksum. hmm.)
        p.hops += 1
        p.ttl -= 1

        # add update neighbor
        self.neighbors[p.send_addr] = Neighbor(rssi=p.rssi, snr=p.snr)
        
        # process aodv control packets
        if p.aodvtype == AODVType.RREQ:
            self._recv_rreq(p)
        elif p.aodvtype == AODVType.RREP:
            self._recv_rrep(p)
        elif p.aodvtype == AODVType.RERR:
            self._recv_rerr(p)
        else:
            # log.warning('recv unrecognized aodv packet')
            self.log('recv unrecognized aodv packet')
    
    def _is_too_recent(self, rreq):
        # 6.5: ignore if in recent rreqs!!
        # first find orig_addr in recent_rreq keys
        if rreq.orig_addr in self.recent_rreqs.keys():
            # then find dest_addr in recent_rreqs[key]
            if rreq.dest_addr in self.recent_rreqs[rreq.orig_addr].keys():
                # ignore old or duplicate rreq
                if rreq.orig_seq <= self.recent_rreqs[rreq.orig_addr][rreq.dest_addr].orig_seq:
                    # log.warning(f'ignoring duplicate rreq: {rreq.orig_addr}')
                    self.log(f'ignoring duplicate rreq: {rreq.orig_addr}')
                    return True
                # update rreq if less hops?
                else:
                    # log.warning(f'got duplicate rreq w/lower hops: {rreq.orig_addr}')
                    self.log(f'got duplicate rreq w/lower hops: {rreq.orig_addr}')
                    return True
            else:
                if len(self.recent_rreqs) >= config.MAX_RECENT_RREQS:
                    # log.warning(f'too many rreqs. blacklisting: {rreq.orig_addr}')
                    self.log(f'too many rreqs. blacklisting: {rreq.orig_addr}')
                return True
                
        else:
            self.recent_rreqs[rreq.orig_addr] = {rreq.dest_addr : RecentRREQ(rreq)}
            self.log(f'added recent rreq: {rreq.orig_addr}')
            return False
    
    # what do on recv rreq
    def _recv_rreq(self, p:Packet):
        # parse the packet
        rreq = RREQ(p.payload)

        # exit if too recent
        if self._is_too_recent(rreq):
            return

        # 6.5.4
        if rreq.orig_addr != self.addr:
            life = (time.time() + 2*config.NET_TRAVERSAL_TIME -
                    2 * p.hops * config.NODE_TRAVERSAL_TIME)
            route = self.routing_table[rreq.orig_addr]
            if route:
                life = max(life, route.lifetime)
            self.routing_table.add_update(addr=rreq.orig_addr, next_hop=p.send_addr,
                                          seq_num=rreq.orig_seq, hops=p.hops,
                                          seq_valid=False, lifetime=life)
            
        # if i am dest, send rrep
        if rreq.dest_addr == self.addr:
            r = RREP()
            r.set_data(dest_addr=self.addr, orig_addr=rreq.orig_addr, dest_seq=self.seq_num)
            # r.set_flags() #TODO ?
            self.tx_fifo.append(Packet().construct(AODVType.RREP, self.addr, p.send_addr, r.pack(), 255))

        # else forward
        else:
            # if route "fresh enough", send rrep, else fwd rreq
            route = self.routing_table[rreq.dest_addr]
            if route and route.valid():
                r = RREP()
                r.set_data(dest_addr=rreq.dest_addr, orig_addr=rreq.orig_addr, dest_seq=route.seq_num)
                # r.set_flags() #TODO ?
                self.tx_fifo.append(Packet().construct(AODVType.RREP, self.addr, p.send_addr, r.pack(), 255))

            else:
                self.routing_table.add_update(rreq.dest_addr, b'', rreq.dest_seq, 0, 1,)
                self._fwd_packet(p)
        

    # what do on recv rrep
    def _recv_rrep(self, p:Packet):
        r = RREP(p.payload)
        print('\ngot rrep!')
        print(r)
        #TODO

    # what do on recv rerr
    def _recv_rerr(self, p:Packet):
        r = RERR(p.payload)
        print('\ngot rerr!')
        print(r)
        #TODO
    
    def _send_hello(self, addr):
        self.neighbors[addr].retries -= 1
        self.neighbors[addr].reset()
        self.tx_fifo.append(Packet().construct(aodvtype=AODVType.HELLO, send_addr=self.addr, recv_addr=addr, ttl=1))
    
    def _recv_hello(self, p:Packet):
        self.neighbors[p.send_addr] = Neighbor(rssi=p.rssi, snr=p.snr)
        #TODO
    
    def _recv_datagram(self, p:Packet):
        r = DATAGRAM(p.payload)
        #TODO

    # fwd packet, changing just send/recv and checksum
    def _fwd_packet(self, p:Packet, recv_addr:bytes=BROADCAST_ADDR):
        self.log(f'forwarding: {p.send_addr}')
        p.send_addr = self.addr
        p.recv_addr = recv_addr
        self.tx_fifo.append(p.pack())
        #TODO
        
    def _fwd_rrep(self, rrep:RREP):
        #TODO
        pass

    def _send_rreq(self, dest_addr):
        r = RREQ()
        route = self.routing_table[dest_addr]
        if route:
            repair = 1 #TODO
            unknown = 0
            dest_seq = route.seq_num
        else:
            repair = 0
            unknown = 1
            dest_seq = 0
        
        # 6.1: increment seq_num before rreq
        self.seq_num = uincr(self.seq_num)
        self.rreq_id = uincr(self.rreq_id)
            
        r.set_flags(0, repair, 0, 0, unknown)
        r.set_data(dest_addr, self.addr, dest_seq, self.seq_num, self.rreq_id)
        self.tx_fifo.append(Packet().construct(AODVType.RREQ, self.addr, BROADCAST_ADDR, r.pack(), 255))
        self.log(f'sending rreq: {dest_addr}')

if __name__ == '__main__':
    p = Packet()
    r = RREQ()
    n = Node(DUMMY_ADDR)

    r.set_flags(join=1, repair=0, dest_only=0, gratuitous=1, unknown=1)
    r.set_data(dest_addr=b'\x13'*8, orig_addr=b'\x3d'*8, dest_seq=0, orig_seq=32, rreq_id=5)
    a = p.construct(AODVType.RREQ, b'\x36'*8, payload=r.pack())


    # recv valid packet
    n.on_recv(a, -137, -65)
    print(n)

    # ingest
    n.update()
    print(n)

    # # recv invalid packet
    # a += b'\x11'
    # n.on_recv(a, -137, -65)