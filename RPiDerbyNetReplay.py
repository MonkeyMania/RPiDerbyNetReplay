import requests
import time
import os
from xml.etree import ElementTree
from subprocess import Popen

thisframerate = 90
Replayurl = "http://192.168.1.134/action.php"
Pstatus = -1
PreplayFin = 0
playbackstarted = False
playbackduration = 15
checkInInt = 1

Replayparams = {'action':'replay-message', 'status':Pstatus, 'finished-replay':PreplayFin}

def ReplayCheckIn():
    r = requests.post(url = Replayurl, data = Replayparams)
    gotthemessage = False

    tree = ElementTree.fromstring(r.content)

    for elem in tree.iter():
        if elem.tag == "replay-message":
            replaymessage = elem.text.split(" ")
            gotthemessage = True
    if gotthemessage:
        return replaymessage
    else:
        return "NORESPONSE"

LastCheckIn = time.time() - 30

while True:
    curTime = time.time()
    #is it time to check in?
    if curTime - LastCheckIn > checkInInt:
        responseList = ReplayCheckIn()
        PreplayFin = 0
        LastCheckIn = curTime
        print("checked in",responseList)
        
        if responseList[0] == "HELLO":
            Pstatus = 0
            print("Hello!")
        if responseList[0] == "TEST":
            Pstatus = 2
            print("Testing!"," Skipback=",responseList[1]," Showings=",responseList[2]," Rate=",responseList[3])
            omxc = Popen(['omxplayer', "Dec2318/race1.mp4"])
            playbackstarted = True
            playbackstart = time.time()
        if responseList[0] == "START":
            Pstatus = 1
        if responseList[0] == "REPLAY":
            Pstatus = 2
        if responseList[0] == "CANCEL":
            Pstatus = 0
        if responseList[0] == "NORESPONSE":
            Pstatus = 0
            print("No updates")
            
    if playbackstarted == True and curTime - playbackstart > playbackduration:
        playbackstarted = False
        PreplayFin = 1
        print("playback Complete")
        


