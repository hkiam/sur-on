text = ""
with open("/tmp/log.bin","rt") as fi:
    text = fi.read()


import re



#S:93:o:69:l:25
print(len(text))
r1 = re.findall(r"S:(\d+):o:(\d+):l:(\d+)", text)

hist = {}
for e in r1:
    hist[int(e[2])] = hist.get(int(e[2]),0) + 1

print("glitchlen")
hist = {k: v for k, v in sorted(hist.items(), key=lambda item: item[1], reverse=True)}
print(hist)

hist = {}
for e in r1:
    hist[int(e[1])] = hist.get(int(e[1]),0) + 1
print("glitchoffset")
hist = {k: v for k, v in sorted(hist.items(), key=lambda item: item[1], reverse=True)}
print(hist)