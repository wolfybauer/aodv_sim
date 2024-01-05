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
    def remaining(self):
        if self.alive:
            return int(self.timestamp + self.lifetime - time.time())
        else:
            return 0

# blacklisted node
class BadNode(Expirable):
    def __init__(self, orig_addr):
        super().__init__(lifetime=config.BLACKLIST_TIMEOUT)
        self.orig_addr = orig_addr


# outbox data waiting for valid route
class QueuedData(Expirable):
    def __init__(self, dest_addr, data):
        super().__init__(config.DATA_QUEUE_TIMEOUT)
        self.dest_addr = dest_addr
        self.data = data


# expirable rreq structure, pass it a RREQ
# for blacklisting nodes exhibiting strange behavior
class RecentRREQ(Expirable):
    def __eq__(self, other):
        return (self.orig_addr == other.orig_addr and
                self.rreq_id == other.rreq_id)
    def __init__(self, rreq:RREQ):
        super().__init__(lifetime=config.PATH_DISCOVERY_TIME)
        self.orig_addr = rreq.orig_addr
        self.rreq_id = rreq.rreq_id

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
    def items(self):
        return self.table.items()
    def __init__(self, my_addr):
        self.addr = my_addr
        self.table = {}
    def update(self):
        for route in self.table.values():
            route.update()
    def add_update(self, addr:bytes, next_hop:bytes=b'', seq_num=0, hops=0, seq_valid=False, lifetime=config.ACTIVE_ROUTE_TIMEOUT):
        if addr == self.addr:
            return False
        old = self.table.get(addr)
        if old:
            if ((seq_num - old.seq_num < 0) or
                (seq_num == old.seq_num and hops < old.hops) or
                (seq_valid and not old.valid())):
                pass
            else:
                return False
        self.table[addr] = Route(next_hop=next_hop, seq_num=seq_num, hops=hops, seq_valid=seq_valid, lifetime=lifetime)
        return True
    def precursors(self, neighbor_addr:bytes):
        return [v.next_hop for k,v in self.table.items() if k == neighbor_addr]

class Node:
    def __repr__(self):
        out = f'NODE:[{self.nickname}]{self.addr}\nSEQ:{self.seq_num},RREQID:{self.rreq_id},'
        out += f'INBOX:{len(self.rx_fifo)},OUTBOX:{len(self.tx_fifo)}\n'
        out += ' == ROUTES == \n'
        out += self.routing_table.__repr__()
        out += '\n == RECENTS == \n'
        out += '\n' + ','.join([str(r) for r in self.recent_rreqs])
        return out
    
    def __init__(self, node_addr:bytes, nickname:str=''):

        self.addr = conform_address(node_addr)
        self.nickname = nickname

        self.seq_num = 0
        self.rreq_id = 0

        # store known routes. { 8-byte addr : Route() }
        self.routing_table = RoutingTable(self.addr)

        # aka precursors. handle rerrs etc
        self.neighbors = {}

        # store recent received rreqs {orig_addr : {dest_addr : orig_seq}}
        self.recent_rreqs = []

        # blacklist nodes exhibiting strange/malicious behavior
        self.blacklist = []

        # packet mailboxes
        self.rx_fifo = deque((), config.PACKET_INBOX_SZ)
        self.tx_fifo = deque((), config.PACKET_OUTBOX_SZ)

        # queued outgoing messages
        self.tx_queued = []
        self.rx_queued = deque((), config.PACKET_INBOX_SZ)

    
    # return nickname if exists, else addr string
    def whoami(self) -> str:
        if self.nickname:
            return self.nickname
        else:
            return hexlify(self.addr).decode('ascii')
    
    def pop_rx(self):
        if len(self.rx_queued):
            return self.rx_queued.popleft()
        return None
    
    # MAIN RECV CALLBACK. if valid, packetize, add to inbox
    # all routing stuff handled internally
    # incoming datagrams will show up in data inbox
    def on_recv(self, raw:bytes, rssi=0, snr=0):
        try:
            p = Packet(raw, rssi, snr)
            self.rx_fifo.append(p)
            log.debug(f'{self.whoami()}:recv packet: {p.send_addr}')
        except PacketBadCrcError:
            log.debug(f'{self.whoami()}:recv bad checksum, ignoring packet')
        except PacketBadLenError:
            log.debug(f'{self.whoami()}:recv bad len, ignoring packet')
    
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
                    rm.append(k)
        for k in rm:
            log.info(f'{self.whoami()}:expired neighbor: {k}')
            del self.neighbors[k]

        # 6.5: update, purge expired recent rreqs
        for i,_ in enumerate(self.recent_rreqs):
            self.recent_rreqs[i].update()
            if not self.recent_rreqs[i].alive:
                r = self.recent_rreqs.pop(i)
                log.debug(f'{self.whoami()}:rm recent rreq: {r}')
                

        # count down route lifetimes
        self.routing_table.update()
        
        # update blacklist
        for i,_ in enumerate(self.blacklist):
            self.blacklist[i].update()
            if not self.blacklist[i].alive:
                n = self.blacklist.pop(i)
                log.warning(f'{self.whoami()}:unblacklisting: {n}')
        
        # update queued data
        for i,d in enumerate(self.tx_queued):
            route = self.routing_table[d.dest_addr]
            if route and route.valid():
                log.info(f'{self.whoami()}:found route for queued: {d}')
                dd = self.tx_queued.pop(i)
                self._send_data(dd.dest_addr, dd.data)
            else:
                self.tx_queued[i].update()
                if not self.tx_queued[i].alive:
                    log.warning(f'{self.whoami()}:expired queued data: {d}')
                    self.tx_queued.pop(i)


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
        
        # if active neighbor, send immediately
        neighbor = self.neighbors.get(dest_addr)
        if neighbor and neighbor.alive:
            self._send_data(dest_addr, data)
            return
        
        # else look for route
        route = self.routing_table[dest_addr]

        # If route exists, send data
        if route and route.valid():
            self._send_data(dest_addr, data)
        else:
            # No valid route, initiate route discovery (RREQ)
            self._send_rreq(dest_addr)
            # queue data until route found
            self.tx_queued.append(QueuedData(dest_addr, data))
        
    # only called when valid route exists
    # push packets into the tx fifo
    def _send_data(self, dest_addr:bytes, data:str):
        
        
        d = DATAGRAM()
        p = Packet()
        
        # if dest is active neighbor, send directly
        if (dest_addr in self.neighbors.keys() and
            self.neighbors[dest_addr].alive):
            recv_addr = dest_addr
            ttl = 1
        else:
            # else get unicast address, aka next hop
            recv_addr = self.routing_table[dest_addr].next_hop
            ttl = self.routing_table[dest_addr].hops

        # data fits in single packet
        if len(data) <= PAYLOAD_MAX_LEN:
            self.seq_num += 1
            d.set_data(dest_addr=dest_addr, orig_addr=self.addr, orig_seq=self.seq_num, data=data)
            self.tx_fifo.append(p.construct(AODVType.DATA, self.addr, recv_addr, d.pack(), ttl))
        # data too big for one packet
        else:
            i = 0
            while i < len(data):
                self.seq_num += 1
                d.set_data(dest_addr=dest_addr, orig_addr=self.addr, orig_seq=self.seq_num, data=data[i:i+PAYLOAD_MAX_LEN])
                self.tx_fifo.append(p.construct(AODVType.DATA, self.addr, recv_addr, d.pack(), ttl))
                i += PAYLOAD_MAX_LEN

    # process inbox
    def _process_rx(self):
        # exit if inbox empty
        if not len(self.rx_fifo):
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
        elif p.aodvtype == AODVType.DATA:
            self._recv_data(p)
        elif p.aodvtype == AODVType.HELLO:
            self._recv_hello(p)
        else:
            # log.warning('recv unrecognized aodv packet')
            log.warning('recv unrecognized aodv packet')
            return
        
        # add route to neighbor
        self.routing_table.add_update(addr=p.send_addr, next_hop=p.send_addr,
                                        seq_num=0, hops=1,
                                        seq_valid=False, lifetime=config.ACTIVE_ROUTE_TIMEOUT)
    
    def _is_too_recent(self, rreq):
        # 6.5: ignore if in recent rreqs!!
        # first find orig_addr in recent_rreq keys
        if rreq in self.recent_rreqs:
            log.debug(f'{self.whoami()}:ignoring duplicate rreq: {rreq.orig_addr}')
            return True
        else:
            self.recent_rreqs.append(RecentRREQ(rreq))
            log.debug(f'{self.whoami()}:added recent rreq: {rreq.orig_addr}')
            return False
    
    # what do on recv rreq
    def _recv_rreq(self, p:Packet):
        # parse the packet
        rreq = RREQ(p.payload)

        # exit if too recent
        if self._is_too_recent(rreq):
            return
        # exit if rreq is one of mine
        if rreq.orig_addr == self.addr:
            return
        
        # 6.5.4 cal origin route lifetime
        life = (2*config.NET_TRAVERSAL_TIME -
                2 * p.hops * config.NODE_TRAVERSAL_TIME)
        
        route = self.routing_table[rreq.orig_addr]
        if route:
            life = max(life, route.lifetime)
        
        # add route to origin
        self.routing_table.add_update(addr=rreq.orig_addr, next_hop=p.send_addr,
                                        seq_num=rreq.orig_seq, hops=p.hops,
                                        seq_valid=True, lifetime=life)
            
        # 6.6.1 route reply generation by the destination
        if rreq.dest_addr == self.addr:
            r = RREP()
            # 6.6.1 weird language
            if uincr(self.seq_num) == rreq.dest_seq:
                self.seq_num = uincr(self.seq_num)
            
            r.set_data(dest_addr=self.addr, orig_addr=rreq.orig_addr, dest_seq=self.seq_num, hop_count=p.hops, lifetime=config.MY_ROUTE_TIMEOUT)
            
            # r.set_flags() #TODO ?
            self.tx_fifo.append(p.construct(AODVType.RREP, self.addr, p.send_addr, r.pack(), ttl=r.hop_count))

        # else forward
        else:
            # 6.6.2 not dest but fresh enough route
            route = self.routing_table[rreq.dest_addr]
            if route and route.valid() and not rreq.dest_only:
                r = RREP()
                r.set_data(dest_addr=rreq.dest_addr, orig_addr=rreq.orig_addr, dest_seq=route.seq_num, hop_count=route.hops+p.hops, lifetime=route.remaining())
                # r.set_flags() #TODO ?
                self.tx_fifo.append(p.construct(AODVType.RREP, self.addr, p.send_addr, r.pack(), ttl=route.hops+p.hops))
                # 6.6.3 gratuitous rreps
                if rreq.gratuitous:
                    log.info(f'{self.whoami()}:send gratuitous rrep:{rreq.dest_addr}')
                    # next hop is dest route next hop
                    next_hop = route.next_hop
                    # must unicast rrep to dest
                    route = self.routing_table[rreq.orig_addr]
                    r.set_data(dest_addr=rreq.orig_addr, orig_addr=rreq.dest_addr, dest_seq=rreq.orig_seq, hop_count=route.hops, lifetime=route.remaining())
                    # r.set_flags()
                    self.tx_fifo.append(Packet().construct(AODVType.RREP, self.addr, next_hop, r.pack(), ttl=route.hops))

            else:
                self.routing_table.add_update(addr=rreq.dest_addr, next_hop=b'', seq_num=rreq.dest_seq, hops=0, seq_valid=False)
                self._fwd_packet(p)
        

    # 6.7 receiving + forwarding rreps
    def _recv_rrep(self, p:Packet):
        rrep = RREP(p.payload)
        # create route to sender of rrep if not exists
        # shortcut: route is valid if dest == sender
        if rrep.dest_addr == p.send_addr:
            seq_num = rrep.dest_seq
            is_neighbor = True
        else:
            seq_num = 0
            is_neighbor = False
        
        # add neighbor route
        self.routing_table.add_update(addr=p.send_addr, next_hop=p.send_addr, seq_num=seq_num, hops=1, seq_valid=is_neighbor)
        
        # next increment hop count
        rrep.hop_count += 1
        
        # create route to dest if not exists
        self.routing_table.add_update(addr=rrep.dest_addr, next_hop=p.send_addr, seq_num=rrep.dest_seq, hops=rrep.hop_count, seq_valid=True, lifetime=rrep.lifetime)
        
        # forward if i am not dest
        if rrep.dest_addr != self.addr:
            # update rrep lifetime
            rrep.lifetime = max(rrep.lifetime, config.ACTIVE_ROUTE_TIMEOUT)
            # get route back to origin
            route = self.routing_table[rrep.orig_addr]
            if route and route.valid() and p.recv_addr == self.addr:
                log.debug(f'{self.whoami()}:fwd rrep. dest:{rrep.dest_addr} ttl:{p.ttl}')
                p.payload = rrep.pack()
                p.payload_len = len(p.payload)
                self._fwd_packet(p, route.next_hop)
            else:
                # log.warning('rrep fwd IGNORED')
                #TODO ?
                pass
        
        # 6.8 handling rrep ack
        if rrep.req_ack:
            #TODO
            pass

    # what do on recv rerr
    def _recv_rerr(self, p:Packet):
        rrer = RERR(p.payload)
        print('\ngot rerr!')
        print(r)
        #TODO
    
    def _send_hello(self, addr):
        self.neighbors[addr].retries -= 1
        self.neighbors[addr].reset(config.HELLO_LIFETIME)
        h = HELLO()
        h.dest_addr = self.addr
        h.dest_seq = self.seq_num
        h.lifetime = config.HELLO_LIFETIME
        p = Packet()
        self.tx_fifo.append(p.construct(aodvtype=AODVType.HELLO, send_addr=self.addr, recv_addr=addr, payload=h.pack(), ttl=1))
    
    def _recv_hello(self, p:Packet):
        h = HELLO(p.payload)
        self.neighbors[p.send_addr] = Neighbor(rssi=p.rssi, snr=p.snr)
        self.routing_table.add_update(h.dest_addr, h.dest_addr, h.dest_seq, hops=1, seq_valid=True, lifetime=config.ACTIVE_ROUTE_TIMEOUT)
    
    def _recv_data(self, p:Packet):
        r = DATAGRAM(p.payload)

        # update orig route everytime
        self.routing_table.add_update(addr=r.orig_addr, next_hop=p.send_addr, seq_num=r.orig_seq, hops=p.hops, seq_valid=True)
        
        # only unicast!
        if p.recv_addr == self.addr:
            if r.dest_addr == self.addr:
                log.info(f'{self.whoami()}:recv datagram:{r.data}')
                if r.data == b'ping':
                    log.info(f'{self.whoami()}:send pong:{r.orig_addr}')
                    self.send(r.orig_addr, 'pong')
                self.rx_queued.append(r)
            elif r.dest_addr in self.neighbors.keys():
                self._fwd_packet(p, r.dest_addr)
            else:
                route = self.routing_table[r.dest_addr]
                if route and route.valid():
                    self._fwd_packet(p, route.next_hop)
                else:
                    log.warning(f'{self.whoami()}:ignore: unrouteable datagram {r.orig_addr}>>>{r.dest_addr}')
                    #TODO send rerr?
                    self._send_rerr()

    # fwd packet, changing just send/recv and checksum
    def _fwd_packet(self, p:Packet, recv_addr:bytes=BROADCAST_ADDR):
        if p.ttl > 0:
            log.debug(f'{self.whoami()}:fwd: {p.send_addr}')
            p.send_addr = self.addr
            p.recv_addr = recv_addr
            self.tx_fifo.append(p.pack())

    def _send_rreq(self, dest_addr, gratuitous=True):
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
            
        r.set_flags(join=False, repair=repair, gratuitous=gratuitous, dest_only=False, unknown=unknown)
        r.set_data(dest_addr, self.addr, dest_seq, self.seq_num, self.rreq_id)
        self.tx_fifo.append(Packet().construct(AODVType.RREQ, self.addr, BROADCAST_ADDR, r.pack(), config.NET_DIAMETER))
        log.debug(f'{self.whoami()}:send rreq: {dest_addr}')
    
    def _send_rerr(self, broken_neighbor_addr:bytes):
        pre = self.routing_table.precursors(broken_neighbor_addr)
        print(pre)

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