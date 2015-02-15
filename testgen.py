from pyethereum import opcodes, utils, blocks, vm, processblock, transactions
from pyethereum.db import DB
import tempfile
import random
import json
pb, u = processblock, utils

db = DB(utils.db_path(tempfile.mktemp()))

push_params = [range(1, 3), range(4, 8), range(9, 16), range(17, 32)]
codesize_params = [[50, 50]]


def generate_op_tests():
    outs = {}
    for opcode, (name, inargs, outargs, _) in opcodes.opcodes.items():
     _subid = 0
     for push_depths in push_params:
      for jump_num, code_size in codesize_params:
        if name in ['CALL', 'CREATE', 'CALLCODE', 'LOG', 'POP', 'RETURN', 'STOP', 'INVALID', 'JUMP', 'JUMPI', 'CALLDATALOAD', 'CALLDATACOPY', 'CODECOPY', 'EXTCODECOPY', 'SHA3', 'MLOAD', 'MSTORE', 'MSTORE8', 'SUICIDE']:
            continue
        if name[:3] in ['DUP', 'SWA', 'LOG']:
            continue
        if name == 'SSTORE':
            jump_num /= 10
        c = '\x5b'
        if name[:4] == 'PUSH':
            if push_depths != push_params[0]:
                continue
            for i in range(code_size):
                v = int(name[4:])
                w = random.randrange(256**v)
                c += chr(0x5f + v) + utils.zpad(utils.encode_int(w), v)
        else:
            for i in range(code_size):
                for _ in range(inargs):
                    v = push_depths[i * len(push_depths) // code_size]
                    w = random.randrange(256**v)
                    c += chr(0x5f + v) + utils.zpad(utils.encode_int(w), v)
                c += chr(opcode)
                for _ in range(outargs):
                    c += chr(0x50)
        # PUSH1 0 MLOAD . DUP1 . PUSH1 1 ADD PUSH1 0 MSTORE . PUSH2 <jumps> GT PUSH1 0 JUMPI
        c += '\x60\x00\x51' + '\x80' + '\x60\x01\x01\x60\x00\x52' + \
            '\x61'+chr(jump_num // 256) + chr(jump_num % 256) + '\x11\x60\x00\x57'
        o = {
            "callcreates": [],
            "env": {
                "currentCoinbase": "2adc25665018aa1fe0e6bc666dac8fc2697ff9ba",
                "currentDifficulty": "256",
                "currentGasLimit": "1000000000",
                "currentNumber": "257",
                "currentTimestamp": "1",
                "previousHash": "5e20a0453cecd065ea59c37ac63e079ee08998b6045136a8ce6635c7912ec0b6"
            },
            "exec": {
                "address": "0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6",
                "caller": "0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6",
                "code": "0x"+c.encode('hex'),
                "data": "0x",
                "gas": "1000000",
                "gasPrice": "100000000000000",
                "origin": "cd1722f3947def4cf144679da39c4c32bdc35681",
                "value": "1000000000000000000"
            },
            "pre": {
                "0f572e5295c57f15886f9b263e2f6d2d6c7b5ec6": {
                    "balance": "1000000000000000000",
                    "code": "0x",
                    "nonce": "0",
                    "storage": {
                    }
                }
            },
            "gas": "1000000",
            "logs": [],
            "out": "0x"
        }
        env = o['env']
        pre = o['pre']
        exek = o['exec']
        blk = blocks.Block(db,
                           prevhash=env['previousHash'].decode('hex'),
                           number=int(env['currentNumber']),
                           coinbase=env['currentCoinbase'],
                           difficulty=int(env['currentDifficulty']),
                           gas_limit=int(env['currentGasLimit']),
                           timestamp=int(env['currentTimestamp']))

        # setup state
        for address, h in pre.items():
            blk.set_nonce(address, int(h['nonce']))
            blk.set_balance(address, int(h['balance']))
            blk.set_code(address, h['code'][2:].decode('hex'))
            for k, v in h['storage'].iteritems():
                blk.set_storage_data(address,
                                     u.big_endian_to_int(k[2:].decode('hex')),
                                     u.big_endian_to_int(v[2:].decode('hex')))

        # execute transactions
        sender = exek['caller']  # a party that originates a call
        recvaddr = exek['address']
        tx = transactions.Transaction(
            nonce=blk._get_acct_item(exek['caller'], 'nonce'),
            gasprice=int(exek['gasPrice']),
            startgas=int(exek['gas']),
            to=recvaddr,
            value=int(exek['value']),
            data=exek['data'][2:].decode('hex'))
        tx.sender = sender

        ext = pb.VMExt(blk, tx)

        def blkhash(n):
            if n >= ext.block_number or n < ext.block_number - 256:
                return ''
            else:
                return u.sha3(str(n))

        ext.block_hash = blkhash

        msg = vm.Message(tx.sender, tx.to, tx.value, tx.startgas,
                         vm.CallData([ord(x) for x in tx.data]))
        success, gas_remained, output = \
            vm.vm_execute(ext, msg, exek['code'][2:].decode('hex'))

        o['post'] = blk.to_dict(True)['state']
        outs[name+str(_subid)] = o
        _subid += 1
    return outs

print json.dumps(generate_op_tests(), indent=4)
