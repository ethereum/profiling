import json, ast
from pyethereum import transactions
from pyethereum import blocks
from pyethereum import processblock as pb
from pyethereum import utils as u
from pyethereum import vm
from pyethereum.slogging import get_logger, LogRecorder, configure_logging
import time
from pyethereum.db import DB
import tempfile
import os
import sys

sys.setrecursionlimit(10000)

db = DB(u.db_path(tempfile.mktemp()))


def profile_vm_test(params):
    pre = params['pre']
    exek = params['exec']
    env = params['env']

    # setup env
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
    blk2 = blocks.Block.deserialize(db, blk.serialize())
    t1 = time.time()
    success, gas_remained, output = \
        vm.vm_execute(ext, msg, exek['code'][2:].decode('hex'))
    blk.commit_state()
    t2 = time.time()
    recorder = LogRecorder()
    ext = pb.VMExt(blk2, tx)
    ext.block_hash = blkhash
    success, gas_remained, output = \
        vm.vm_execute(ext, msg, exek['code'][2:].decode('hex'))
    trace = recorder.pop_records()
    ops = [x['op'] for x in trace if x['event'] == 'vm']
    opdict = {}
    for op in ops:
        opdict[op] = opdict.get(op, 0) + 1
    return {"ops": opdict, "time": t2 - t1}


def prepare_state_test(params):

    pre = params['pre']
    exek = params['transaction']
    env = params['env']
    # setup env
    blk = blocks.Block(db,
                       prevhash=env['previousHash'].decode('hex'),
                       number=int(env['currentNumber']),
                       coinbase=env['currentCoinbase'],
                       difficulty=int(env['currentDifficulty']),
                       gas_limit=int(env['currentGasLimit']),
                       timestamp=int(env['currentTimestamp']))

    for address, h in pre.items():
        blk.set_nonce(address, int(h['nonce']))
        blk.set_balance(address, int(h['balance']))
        blk.set_code(address, h['code'][2:].decode('hex'))
        for k, v in h['storage'].iteritems():
            blk.set_storage_data(address,
                                 u.big_endian_to_int(k[2:].decode('hex')),
                                 u.big_endian_to_int(v[2:].decode('hex')))

    # execute transactions
    tx = transactions.Transaction(
        nonce=int(exek['nonce'] or "0"),
        gasprice=int(exek['gasPrice'] or "0"),
        startgas=int(exek['gasLimit'] or "0"),
        to=exek['to'],
        value=int(exek['value'] or "0"),
        data=exek['data'][2:].decode('hex')).sign(exek['secretKey'])

    orig_apply_msg = pb.apply_msg

    def apply_msg_wrapper(ext, msg, code):

        def blkhash(n):
            if n >= blk.number or n < blk.number - 256:
                return ''
            else:
                return u.sha3(str(n))

        ext.block_hash = blkhash
        return orig_apply_msg(ext, msg, code)

    pb.apply_msg = apply_msg_wrapper

    blk2 = blocks.Block.deserialize(db, blk.serialize())
    t1 = time.time()
    try:
        pb.apply_transaction(blk, tx)
    except:
        print 'exception'
        pass
    t2 = time.time()
    recorder = LogRecorder()
    try:
        pb.apply_transaction(blk2, tx)
    except:
        print 'exception'
        pass
    trace = recorder.pop_records()
    ops = [x['op'] for x in trace if x['event'] == 'vm']
    opdict = {}
    for op in ops:
        opdict[op] = opdict.get(op, 0) + 1
    return {"ops": opdict, "time": t2 - t1}


def recursive_list(d):
    files = []
    dirs = [d]
    i = 0
    while i < len(dirs):
        if os.path.isdir(dirs[i]):
            children = [os.path.join(dirs[i], f) for f in os.listdir(dirs[i])]
            for f in children:
                dirs.append(f)
        elif dirs[i][-5:] == '.json':
                files.append(dirs[i])
        i += 1
    return files


def prepare_files(vm_files):
    o = []
    for i, f in enumerate(vm_files):
        j = json.load(open(f))
        for _, t in j.items():
            o.append(profile_vm_test(t))
    # for i, f in enumerate(state_files):
    #     j = json.load(open(f))
    #     for _, t in j.items():
    #         o.append(prepare_state_test(t))
    #         if not o[-1]["ops"]:
    #             o.pop()
    return o

print json.dumps(prepare_files(recursive_list(sys.args[1])), indent=4)
