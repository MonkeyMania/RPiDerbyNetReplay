import requests
import time
import os
import picamera
import pygame.display
from xml.etree import ElementTree
from subprocess import Popen
################ END IMPORTS ################

################ START DERBYNET CONFIG ################
derbynetserverIP = "192.168.1.134"
checkInInt = 1
################ END DERBYNET CONFIG ################
################ START REPLAY CONFIG ################
isoVal = 0
expmode = 'sports'
thisframerate = 90
testfilename = "race1.mp4"
################ END REPLAY CONFIG ################
################ START SETUP GLOBALS ################
replayurl = derbynetserverIP + "/action.php"
Pstatus = -1
PreplayFin = 0
playbackstarted = False
################ END SETUP GLOBALS ################
################ START SETUP CAMERA ################
camera = picamera.PiCamera()
camera.vflip = True
camera.hflip = True
camera.resolution = (640, 480)
camera.framerate = thisframerate
camera.exposure_mode = 'sports'
camera.iso = isoVal
stream = picamera.PiCameraCircularIO(camera, seconds=7)
################ END SETUP CAMERA ################
################ START CREATE VIDEO DIRECTORY ################
dirpref = time.strftime("%Y-%m-%d recordings")
directory = dirpref + "/"
os.makedirs(directory)
################ END CREATE VIDEO DIRECTORY ################

################ START FUNCTIONS ################
# function for checking in with the server - here for cleanliness of main code
def ReplayCheckIn(strURL, strData):
        r = requests.post(url = strURL, data = strData)
        print(r.url)

        tree = ElementTree.fromstring(r.content)

        gotthemessage = False
        for elem in tree.iter():
                if elem.tag == "replay-message":
                        replaymessage = elem.text.split(" ")
                        gotthemessage = True
        if gotthemessage:
                return replaymessage
        else:
                return "NORESPONSE"

# function for toggling the screen to be blanked or not - here due to repeated use      
def ScreenBlanked(toggle = True):
        if toggle == True:
                #set blank screen behind everything
                pygame.display.init()
                screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                screen.fill((0, 0, 0))
        else:
                pygame.display.quit()

################ END FUNCTIONS ################

# Setup last checkin to ensure triggered on first run
LastCheckIn = time.time() - 30

try:
        while True:
                curTime = time.time()
                #is it time to check in?
                if curTime - LastCheckIn > checkInInt:
                        Replayparams = {'action':'replay-message', 'status':Pstatus, 'finished-replay':PreplayFin}
                        responseList = ReplayCheckIn(replayurl, Replayparams)
                        # Reset replayfin after last POST to only send one scan of 1
                        PreplayFin = 0
                        LastCheckIn = curTime
                        print("checked in",responseList)
            
                if responseList[0] == "HELLO":
                        Pstatus = 0
                        camera.stop_recording()
                        camera.stop_preview()
                        ScreenBlanked(False)
                        print("Hello!")
                if responseList[0] == "TEST":
                        # Ensure we only do something when nothing else was happening
                        if Pstatus == 0:
                                Pstatus = 2
                                print("Testing!"," Skipback=",responseList[1]," Showings=",responseList[2]," Rate=",responseList[3])
                                ScreenBlanked(True)
                                filemp4 = testfilename
                                replaycount = 0
                                showings = responseList[2]
                                playbackstarted = False
                                playbackduration = 15
                if responseList[0] == "START":
                        Pstatus = 1
                        ScreenBlanked(True)
                        filemp4 = directory + time.strftime("%H%M%s_") + responseList[1] + ".mp4"
                        filename = directory + time.strftime("%H%M%s_") + responseList[1] + ".h264"
                        camera.start_recording(stream, format='h264', intra_period = 10)
                        camera.start_preview()
                if responseList[0] == "REPLAY":
                        # only do something if we get this while recording
                        # which also means we should have filenames defined
                        if Pstatus == 1:
                                Pstatus = 2
                                # Save requested last few seconds
                                # I'm assuming here that REPLAY comes AFTER last car crosses
                                stream.copy_to(filename, seconds=responseList[1])
                                # playback with h264 is wonky, convert to mp4
                                convertstring = "MP4Box -fps " + str(thisframerate * responseList[3]) + " -add " + filename + " " + filemp4
                                os.system(convertstring)
                                camera.stop_preview()
                                replaycount = 0
                                showings = responseList[2]
                                playbackstarted = False
                                # Estimate and pad playback time
                                playbackduration = responseList[1] / responseList[3] + 2
                if responseList[0] == "CANCEL":
                        Pstatus = 0
                        camera.stop_recording()
                        camera.stop_preview()
                        ScreenBlanked(False)
                if responseList[0] == "NORESPONSE":
                        print("No updates")
        
        # We're in playback mode
        if Pstatus == 2:
                # Are we currently playing back?
                if playbackstarted == True:
                        # Is the last playback expected complete?
                        if curTime - playbackstart > playbackduration:
                                playbackstarted = False
                                showings = showings + 1
                                # Was this the last one?
                                if replaycount >= showings:
                                        PreplayFin = 1
                                        Pstatus = 0
                                        ScreenBlanked(False)
                                        print("playback Complete")
                else:
                        # start a playback (playback is false, but we're here)
                        omxc = Popen(['omxplayer', filemp4])
                        playbackstart = curTime
                        playbackstarted = True
        
finally:
        pygame.display.quit()
        camera.stop_recording()
        camera.stop_preview()
        camera.close()
        sys.exit()
