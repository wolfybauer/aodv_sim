import struct

DUMMY_ADDR = b'deadbeef'

BROADCAST_ADDR = b'\xff'*8
PACKET_LEN = 255
HEADER_LEN = 24
DATAGRAM_HEADER_LEN = 20
PAYLOAD_MAX_LEN = PACKET_LEN - HEADER_LEN - DATAGRAM_HEADER_LEN
CHECKSUM_OFFSET = 20

class AODVType:
    UNKNOWN = 0
    RREQ    = 1
    RREP    = 2
    RERR    = 3
    HELLO   = 4
    DATA    = 5
    ACK     = 6


def compute_fletcher_16(data):
    sum_l = 0
    sum_h = 0
    for byte in data:
        sum_l = (sum_l + byte) % 255
        sum_h = (sum_h + sum_l) % 255
    return sum_h << 8 | sum_l

class PacketBadCrcError(Exception):
    pass
class PacketBadLenError(Exception):
    pass

class Packet:
    def __repr__(self):
        return '<'+",".join(f"{k}={v}" for k, v in self.__dict__.items())+'>'
    def __eq__(self, other) -> bool:
        for k,v in self.__dict__.items():
            if not v == other.__dict__[k]:
                return False
        return True
    def __init__(self, raw:bytes=b'', rssi=0, snr=0):
        self.rssi=rssi
        self.snr=snr
        if raw:
            self.deconstruct(raw)
        else:
            self.send_addr = DUMMY_ADDR                # uint64_t (bytes)
            self.recv_addr = DUMMY_ADDR                # uint64_t (bytes)
            self.aodvtype = AODVType.UNKNOWN          # uint8_t
            self.hops = 0                       # uint8_t
            self.ttl = 0                        # uint8_t
            self.payload_len = 0                # uint8_t
            self.checksum = 0                   # uint16_t
            self.reserved = 0                   # uint16_t

            self.header = b''
            self.payload = b''

    def construct(self, aodvtype:int, send_addr:bytes, recv_addr:bytes=BROADCAST_ADDR, payload:bytes=b'', ttl:int=0, hops:int=0):
        self.send_addr = send_addr
        self.recv_addr = recv_addr
        self.aodvtype = aodvtype
        self.payload = payload
        self.payload_len = len(payload)
        self.hops = hops
        self.ttl = ttl
        return self.pack()

    def pack(self):
        self.header = self.send_addr + self.recv_addr + struct.pack('>BBBBHH', self.aodvtype, self.hops, self.ttl, self.payload_len, 0, 0)
        raw = bytearray(self.header+self.payload)
        raw[CHECKSUM_OFFSET] = 0
        raw[CHECKSUM_OFFSET+1] = 0
        self.checksum = compute_fletcher_16(bytes(raw))
        struct.pack_into('>H', raw, CHECKSUM_OFFSET, self.checksum)
        raw = bytes(raw)
        self.header = raw[:HEADER_LEN]
        return raw


    def deconstruct(self, raw:bytes):
        try:
            # split header and payload
            self.header = raw[:HEADER_LEN]
            self.payload = raw[HEADER_LEN:]
            # parse
            self.send_addr = self.header[:8]
            self.recv_addr = self.header[8:16]
            self.aodvtype, self.hops, self.ttl, self.payload_len, self.checksum, self.reserved = struct.unpack('>BBBBHH', self.header[16:])
        except ValueError:
            raise PacketBadLenError
        # get raw sans checksum bytes
        arr = bytearray(raw)
        arr[CHECKSUM_OFFSET] = 0
        arr[CHECKSUM_OFFSET+1] = 0

        # check packet valid
        if not self.checksum == compute_fletcher_16(bytes(arr)):
            # print('invalid crc!')
            raise PacketBadCrcError
        # check payload size valid
        if not self.payload_len == len(self.payload):
            # print('invalid len!')
            raise PacketBadLenError
        
class RREQ:
    def __repr__(self):
        return '<'+",".join(f"{k}={v}" for k, v in self.__dict__.items())+'>'
    def __eq__(self, other) -> bool:
        for k,v in self.__dict__.items():
            if not v == other.__dict__[k]:
                return False
        return True
    def __init__(self, raw:bytes=b''):
        if raw:
            self.unpack(raw)
        else:
            self.join = 0
            self.repair = 0
            self.gratuitous = 0
            self.dest_only = 0
            self.unknown = 0
            self.flags = 0
            self.dest_addr = DUMMY_ADDR
            self.orig_addr = DUMMY_ADDR
            self.dest_seq = 0
            self.orig_seq = 0
            self.rreq_id = 0
    def set_flags(self, join:bool=0, repair:bool=0, gratuitous:bool=0, dest_only:bool=0, unknown:bool=0):
        self.join = join                # bit: join flag (multicast)
        self.repair = repair            # bit: repair flag (multicast)
        self.gratuitous = gratuitous    # bit: gratuitous rrep should be unicast to dest_addr
        self.dest_only = dest_only      # bit: only dest_addr may respond to this rreq
        self.unknown = unknown          # bit: indicates dest_seq is unknown
        self.flags = join<<4 | repair<<3 | gratuitous<<2 | dest_only<<1 | unknown
    def set_data(self, dest_addr:bytes, orig_addr:bytes, dest_seq:int, orig_seq:int, rreq_id:int):
        self.dest_addr = dest_addr      # uint64_t
        self.orig_addr = orig_addr      # uint64_t
        self.dest_seq = dest_seq        # uint32_t
        self.orig_seq = orig_seq        # uint32_t
        self.rreq_id = rreq_id          # uint32_t
    def get_flags(self, flags:int):
        self.join = (flags >> 4) & 1
        self.repair = (flags >> 3) & 1
        self.gratuitous = (flags >> 2) & 1
        self.dest_only = (flags >> 1) & 1
        self.unknown = flags & 1
    def unpack(self, raw:bytes):
        self.dest_addr = raw[:8]
        self.orig_addr = raw[8:16]
        self.dest_seq, self.orig_seq, self.rreq_id, self.flags = struct.unpack('>LLLB', raw[16:])
        self.get_flags(self.flags)
    def pack(self):
        raw = self.dest_addr + self.orig_addr
        raw += struct.pack('>LLLB', self.dest_seq, self.orig_seq, self.rreq_id, self.flags)
        return raw

class RREP:
    def __repr__(self):
        return '<'+",".join(f"{k}={v}" for k, v in self.__dict__.items())+'>'
    def __eq__(self, other) -> bool:
        for k,v in self.__dict__.items():
            if not v == other.__dict__[k]:
                return False
        return True
    def __init__(self, raw:bytes=b''):
        if raw:
            self.unpack(raw)
        else:
            self.repair = 0
            self.req_ack = 0
            self.prefix_sz = 0
            self.flags = 0
            self.dest_addr = DUMMY_ADDR
            self.orig_addr = DUMMY_ADDR
            self.dest_seq = 0
            self.hop_count = 0
            self.lifetime = 0

    def set_flags(self, repair:bool=0, req_ack:bool=0, prefix_sz:int=0):
        self.repair = repair                    # bit: repair flag (multicast)
        self.req_ack = req_ack                  # bit: ack requested flag
        self.prefix_sz = prefix_sz & 0b11111    # 5 bits: if !=0, next hop ok to use by any node with same 5bit prefix as dest_addr
        self.flags = repair<<6 | req_ack<<5 | (prefix_sz & 0b11111)
    def set_data(self, dest_addr:bytes, orig_addr:bytes, dest_seq:int, hop_count:int, lifetime:int):
        self.dest_addr = dest_addr      # uint64_t
        self.orig_addr = orig_addr      # uint64_t
        self.dest_seq = dest_seq        # uint32_t
        self.hop_count = hop_count      # uint8_t
        self.lifetime = lifetime        # uint32_t
    def get_flags(self, flags:int):
        self.repair = (flags>>6) & 1
        self.req_ack = (flags>>5) & 1
        self.prefix_sz = flags & 0b11111
    def unpack(self, raw:bytes):
        self.dest_addr = raw[:8]
        self.orig_addr = raw[8:16]
        self.dest_seq, self.flags, self.hop_count, self.lifetime = struct.unpack('>LBBL', raw[16:])
        self.get_flags(self.flags)
    def pack(self):
        raw = self.dest_addr + self.orig_addr
        raw += struct.pack('>LBBL', self.dest_seq, self.flags, self.hop_count, self.lifetime)
        return raw

class RERR:
    def __repr__(self):
        return '<'+",".join(f"{k}={v}" for k, v in self.__dict__.items())+'>'
    def __eq__(self, other) -> bool:
        for k,v in self.__dict__.items():
            if not v == other.__dict__[k]:
                return False
        return True
    def __init__(self, raw:bytes=b''):
        self.addr_list = []
        self.seq_list = []
        if raw:
            self.unpack(raw)
        else:
            self.bad_addr = b''
            self.bad_seq = 0
            self.no_delete = 0
            self.dest_count = 0
            self.flags = 0
    def set_data(self, bad_addr:bytes, bad_seq:int, addr_list:list[bytes], seq_list:list[int], no_delete:bool):
        if not len(addr_list) == len(seq_list):
            raise IndexError
        self.bad_addr = bad_addr                        # uint64_t
        self.bad_seq = bad_seq                          # uint32_t
        self.no_delete = no_delete                      # bit: node has repaired local link, upstream should NOT delete
        self.dest_count = len(addr_list)                # 5 bits: number of additional broke addr:seq pairs in list
        self.flags = (no_delete<<5) | len(addr_list)
        self.addr_list = addr_list                      # uint64_t * dest_count
        self.seq_list = seq_list                        # uint32_t * dest_count
    def get_flags(self, flags:int):
        self.no_delete = (flags>>5) & 1
        self.dest_count = flags & 0b11111
    def unpack(self, raw:bytes):
        self.bad_addr = raw[:8]
        self.bad_seq, self.flags = struct.unpack('>LB', raw[8:13])
        self.get_flags(self.flags)
        for i in range(13, 12*(self.dest_count+1),12):
            self.addr_list.append(raw[i:i+8])
            self.seq_list.append(int.from_bytes(raw[i+8:i+12], 'big'))
    def pack(self):
        raw = self.bad_addr + struct.pack('>LB', self.bad_seq, self.flags)
        for i in range(self.dest_count):
            raw += self.addr_list[i]
            raw += struct.pack('>L', self.seq_list[i])
        return raw

# # PACKET: ROUTE REPLY ACKNOWLEDGMENT
# class ACK:
#     def __init__(self, send_addr=DUMMY_ADDR, recv_addr=BROADCAST_ADDR):
#         super().__init__(send_addr, recv_addr, AODVType.ACK)
#     def pack(self):
#         return self.header(0)
        

# # PACKET: HELLO
class HELLO(RREP):
    def __init__(self, raw:bytes=b''):
        super().__init__(raw)

class DATAGRAM:
    def __repr__(self):
        return '<'+",".join(f"{k}={v}" for k, v in self.__dict__.items())+'>'
    def __eq__(self, other) -> bool:
        for k,v in self.__dict__.items():
            if not v == other.__dict__[k]:
                return False
        return True
    def __init__(self, raw:bytes=b''):
        if raw:
            self.unpack(raw)
        else:
            self.dest_addr = b''
            self.orig_addr = b''
            self.orig_seq = 0
            self.data = ''
    def set_data(self, dest_addr:bytes, orig_addr:bytes, orig_seq:int, data:str):
        self.dest_addr = dest_addr
        self.orig_addr = orig_addr
        self.orig_seq = orig_seq
        self.data = data
    def unpack(self, raw:bytes):
        data_len = len(raw) - DATAGRAM_HEADER_LEN
        self.dest_addr = raw[:8]
        self.orig_addr = raw[8:16]
        self.orig_seq, self.data = struct.unpack(f'>L{data_len}s', raw[16:])
    def pack(self):
        raw = self.dest_addr + self.orig_addr
        return raw + struct.pack(f'>L{len(self.data)}s', self.orig_seq, self.data.encode('ascii'))




if __name__ == '__main__':
    print('testing RREQ...\n')

    p = Packet()
    r = RREQ()
    r.set_flags(join=1, repair=0, gratuitous=1, unknown=1)
    r.set_data(dest_addr=b'\x13'*8, orig_addr=DUMMY_ADDR, dest_seq=0, orig_seq=32, rreq_id=5)
    a = p.construct(AODVType.RREQ, payload=r.pack(), send_addr=DUMMY_ADDR)

    pp = Packet(a)
    rr = RREQ(pp.payload)

    print(f'ORIGINAL RREQ\n{r}\n')
    print(f'ORIGINAL PACKET\n{p}\n')
    print(f'DERIVED RREQ\n{rr}\n')
    print(f'DERIVED PACKET\n{pp}\n')
    print(f'p == pp:{p==pp}')
    print(f'r == rr:{r==rr}')

    print('\ntesting RREP...\n')

    p = Packet()
    r = RREP()
    r.set_flags(repair=0, req_ack=1, prefix_sz=13)
    r.set_data(dest_addr=b'\x13'*8, orig_addr=DUMMY_ADDR, dest_seq=32, ttl_ms=300)
    a = p.construct(AODVType.RREP, payload=r.pack(), send_addr=DUMMY_ADDR)

    pp = Packet(a)
    rr = RREP(pp.payload)

    print(f'ORIGINAL RREP\n{r}\n')
    print(f'ORIGINAL PACKET\n{p}\n')
    print(f'DERIVED RREP\n{rr}\n')
    print(f'DERIVED PACKET\n{pp}\n')
    print(f'p == pp:{p==pp}')
    print(f'r == rr:{r==rr}')

    print('\ntesting RERR...\n')

    addr_ls = [b'\x3a'*8, b'\x3f'*8, b'\x40'*8]
    seq_ls = [50, 103, 45]

    p = Packet()
    r = RERR()
    r.set_data(bad_addr=b'\x3e'*8, bad_seq=44, addr_list=addr_ls, seq_list=seq_ls, no_delete=0)
    a = p.construct(AODVType.RERR, payload=r.pack(), send_addr=DUMMY_ADDR)

    pp = Packet(a)
    rr = RERR(pp.payload)

    print(f'ORIGINAL RERR\n{r}\n')
    print(f'ORIGINAL PACKET\n{p}\n')
    print(f'DERIVED RERR\n{rr}\n')
    print(f'DERIVED PACKET\n{pp}\n')
    print(f'p == pp:{p==pp}')
    print(f'r == rr:{r==rr}')