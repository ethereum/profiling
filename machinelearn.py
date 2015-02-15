import json
import sys


def spow(b, e):
    return abs(b) ** e * (1 if b > 0 else -1)


def machine_learn_gascosts(jsondata):
    opcounts = [x['ops'] for x in jsondata]
    times = [x['time'] for x in jsondata]
    keys = set()
    for j in opcounts:
        for k in j:
            keys.add(k)
    print "Found %d keys, %d samples" % (len(keys), len(jsondata))
    print keys, '_base' in keys
    keys = ['_base'] + list(keys)
    xs = []
    for j in opcounts:
        datum = [1]
        for k in keys[1:]:
            datum.append(j.get(k, 0))
        xs.append(datum)
    ys = times
    weights = [0.0001] * len(keys)
    for i in range(200):
        score = 0
        scoreprime = [0] * len(weights)
        for x, y in zip(xs, ys):
            tot = 0
            for j, (w, v) in enumerate(zip(weights, x)):
                tot += v * w
            score += (tot - y) ** 2 / y
            for j, (w, v) in enumerate(zip(weights, x)):
                scoreprime[j] += v * 2 * (tot - y) / y
        for j in range(len(weights)):
            weights[j] -= 0.00000001 * spow(scoreprime[j], 0.5)
            weights[j] = max(0, weights[j])
        if i % 1 == 0:
            print "Finished %d rounds, score %f" % (i + 1, score)
    o = {}
    for w, op in zip(weights, keys):
        o[op] = w
    return {"score": score, "out": o}

print machine_learn_gascosts(json.loads(open(sys.argv[1]).read()))
