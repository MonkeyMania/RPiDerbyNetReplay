import requests #For http POST
import time #For sleeping and current time for file and folder creation
import os #For making directories
import picamera
import pygame.display
from xml.etree import ElementTree
from subprocess import Popen
################ END IMPORTS ################

################ START DERBYNET CONFIG ################
derbynetserverIP = "http://192.168.1.134"   #Server that's hosting DerbyNet - NO TRAILING SLASH!
checkinintervalnormal = 1   #seconds between polling server when not racing
checkinintervalracing = 0.25 #seconds between polling server when racing
################ END DERBYNET CONFIG ################
################ START REPLAY CONFIG ################
isoVal = 0
expmode = 'sports'
thisframerate = 90
testfilename = "test.mp4"
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
################ END SETUP CAMERA ################
################ START CREATE VIDEO DIRECTORY ################
dirpref = time.strftime("%Y-%m-%d recordings")
directory = dirpref + "/"
if not os.path.exists(directory):
    os.makedirs(directory)
################ END CREATE VIDEO DIRECTORY ################
################ START FUNCTIONS ################
# function for starting recording
def StartRecording(strFilename):
    camera.start_recording(strFilename, format='h264', intra_period = 10)
    camera.start_preview()

# function for stopping recording
def StopRecording():
    camera.stop_recording()
    camera.stop_preview()

# function for toggling the screen to be blanked or not - here due to repeated use      
def HideTheDesktop(hideIt = True):
    if hideIt:
        #set blank screen behind everything
        #TESTING - COMMENTING OUT ROWS BELOW TO MAKE IT EASIER TO ABORT STUCK PLAYBACK/PREVIEW
        #pygame.display.init()
        #screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        #screen.fill((0, 0, 0))
    else:
        pygame.display.quit()

################ END FUNCTIONS ################
################ START MAIN ROUTINE ################
# Setup last checkin to ensure triggered on first run
lastcheckin = time.time() - 30

# setup polling interval
checkininterval = checkinintervalnormal

# setup camera state for tracking (hates stopping when not running)
currentlyrecording = False

try:
    while True:
        curTime = time.time()
        #is it time to check in?
        if curTime - lastcheckin > checkininterval:
            #Time to check - let's do this
            Replayparams = {'action':'replay-message', 'status':Pstatus, 'finished-replay':PreplayFin}
            r = requests.post(url = replayurl, data = Replayparams)
            #Check we got a valid response
            if r.status_code == requests.codes.ok:
                #Look for the replay-message data
                tree = ElementTree.fromstring(r.content)
                for elem in tree.iter("replay-message"):
                    replaymessage = elem.text.split(" ")
                    print(replaymessage)
                    
                    if replaymessage[0] == "HELLO":
                        Pstatus = 0
                        checkininterval = checkinintervalnormal
                        print("Hello!")
                        
                    if replaymessage[0] == "TEST":
                        # Ensure we only do something when nothing else was happening (otherwise ignored)
                        if Pstatus == 0:
                            Pstatus = 2
                            #TIM-I DON'T THINK I WANT THIS HERE - checkininterval = checkinintervalnormal
                            print("Testing!"," Skipback=",replaymessage[1]," Showings=",replaymessage[2]," Rate=",replaymessage[3])
                            filemp4 = testfilename
                            replaycount = 0
                            showings = max(1,int(replaymessage[2])) #Did this since showing isn't technically in the spec - although might bork on no value
                            replayactive = False
                            playbackduration = 15

                    if replaymessage[0] == "START":
                        fileroot = directory + replaymessage[1] + time.strftime("_%H%M%S")
                        #Since START often comes immediately following REPLAY, I'll just queue it up and if this is true then start recording at that time
                        readytostartrecording = True

                    if replaymessage[0] == "REPLAY" and Pstatus == 1:
                        # only do something if we get this while recording (otherwise ignored since it wouldn't make sense)
                        # which also means we should have filename and starttime defined
                        Pstatus = 2
                        StopRecording()
                        recordingendtime = time.time()
                        currentlyrecording = False
                        # Extract requested last few seconds
                        # playback with h264 is wonky, convert to mp4
                        recordinglength = recordingendtime - recordingstarttime
                        replaystarttime = max(0, recordinglength - replaymessage[1])
                        replayduration = recordinglength - replaystarttime
                        convertstring = "MP4Box -fps " + str(thisframerate * int(replaymessage[3])) + " -splitx " + replaystarttime + ":" + recordinglength + " -add " + fileroot + ".h264 " + fileroot + ".mp4"
                        os.system(convertstring)
                        # Setup for replay
                        replaycount = 0
                        showings = int(replaymessage[2])
                        replayactive = False
                        # Estimate and pad playback time
                        playbackduration = replayduration / float(replaymessage[3]) + 3

                    if replaymessage[0] == "CANCEL" and Pstatus == 1:
                        #This command is only intended for recording, otherwise ignore
                        Pstatus = 0
                        if currentlyrecording:
                            #Yes this seems redundant, but it doesn't like stopping a non-recording a lot
                            StopRecording()
                            currentlyrecording = False
                        checkininterval = checkinintervalnormal
                        #Also intercept any previously setup start recordings in this single response
                        readytostartrecording = False
                        HideTheDesktop(False)
                else:
                    #"NOUPDATES" - add code as needed
            else:
                #"NOCONTACT" - add code as needed
            # Reset replayfin after last POST to only send one scan of 1
            PreplayFin = 0
            lastcheckin = curTime

        # Done with processing the server response, now focus first on doing any replays
        # Then if all replays are done and ready to start recording, do it
        if Pstatus == 2:
            # Are we currently playing back?
            if replayactive:
                # Is the last playback expected complete?
                if curTime - playbackstart > playbackduration:
                    replayactive = False
                    replaycount = replaycount + 1
                    # Was this the last one?
                    if replaycount >= showings:
                        PreplayFin = 1
                        Pstatus = 0
                        HideTheDesktop(False)
            else:
                # start a playback (playback is false, but we're in playback status)
                omxc = Popen(['omxplayer', fileroot + ".mp4"])
                playbackstart = curTime
                replayactive = True
                
        elif readytostartrecording:
            # Start recording
            HideTheDesktop(True)
            StartRecording(fileroot + ".h264")
            recordingstarttime = time.time()
            currentlyrecording = True
            Pstatus = 1

finally:
    HideTheDesktop(False)
    if currentlyrecording:
        camera.stop_recording()
        camera.stop_preview()
    camera.close()
