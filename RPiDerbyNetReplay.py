import requests #For http POST
import time #For sleeping and current time for file and folder creation
import os #For making directories
import picamera
import pygame.display
from xml.etree import ElementTree
from subprocess import Popen
from PIL import Image, ImageDraw, ImageFont
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
testMP4fileroot = "test" # Don't include extension, but must be MP4
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

font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSerif.ttf", 20) 
fontBold = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf", 48)

textPad = Image.new('RGB', (224, 960))
textPadImage = textPad.copy()

imgPad = Image.new('RGB', (224, 224))
imgPadImage = imgPad.copy()

################ END SETUP CAMERA ################
################ START CREATE VIDEO DIRECTORY ################
dirpref = time.strftime("%Y-%m-%d_recordings")
directory = dirpref + "/"
if not os.path.exists(directory):
    os.makedirs(directory)
################ END CREATE VIDEO DIRECTORY ################
################ START FUNCTIONS ################
# function for starting recording
def StartRecording(strFilename, strVideoname):
    #Filename is what to save it as (directory and extension included)
    #Videoname is what it's called for display
    camera.start_recording(strFilename, format='h264', intra_period = 10)
    camera.start_preview()

    #Setup overlays and show them
    textPadImageLeft = textPad.copy()
    drawTextImage = ImageDraw.Draw(textPadImageLeft)
    drawTextImage.text((20, 20),strVideoname[0] , font=fontBold, fill=("Red"))
    overlayleft = camera.add_overlay(textPadImageLeft.tobytes(), size=(224, 960), alpha = 255, layer = 3, fullscreen = False, window = (0,0,224, 960))

    textPadImageRight = textPad.copy()
    drawTextImage = ImageDraw.Draw(textPadImageRight)
    drawTextImage.text((20, 20),strVideoname[1] , font=fontBold, fill=("Yellow"))
    drawTextImage.text((20, 200),strVideoname[2] , font=fontBold, fill=("Yellow"))
    overlayright = camera.add_overlay(textPadImageRight.tobytes(), size=(224, 960), alpha = 255, layer = 3, fullscreen = False, window = (1696,0,224,960))

# function for stopping recording
def StopRecording():
    #camera.remove_overlay(overlayleft)
    #camera.remove_overlay(overlayright)
    camera.stop_recording()
    camera.stop_preview()

# function for toggling the screen to be blanked or not - here due to repeated use      
def HideTheDesktop(hideIt = True):
    if hideIt:
        #set blank screen behind everything
        pygame.display.init()
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        screen.fill((0, 0, 0))
    else:
        pygame.display.quit()

################ END FUNCTIONS ################
################ START MAIN ROUTINE ################
# Setup last checkin to ensure triggered on first run
lastcheckin = time.time() - 30

# setup polling interval
checkininterval = checkinintervalnormal

# setup states for tracking
currentlyrecording = False
readytostartrecording = False

try:
    while True:
        curTime = time.time()
        #is it time to check in?
        if curTime - lastcheckin > checkininterval:
            #Time to check - let's do this
            Replayparams = {'action':'replay-message', 'status':Pstatus, 'finished-replay':PreplayFin}
            print(Replayparams)
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
                            print("Testing!"," Skipback=",replaymessage[1]," Showings=",replaymessage[2]," Rate=",replaymessage[3])
                            fileroot = testMP4fileroot
                            replaycount = 0
                            showings = max(1,int(replaymessage[2])) #Did this since showing isn't technically in the spec - although might bork on no value
                            replayactive = False
                            playbackduration = 15

                    if replaymessage[0] == "START":
                        videonameroot = replaymessage[1].split("_")
                        # Setup filename for next recording, can't just use fileroot as it could be in use for playback
                        nextfileroot = directory + replaymessage[1] + time.strftime("_%H%M%S")
                        #Since START often comes immediately following REPLAY, I'll just queue it up and if this is true then start recording at that time
                        readytostartrecording = True

                    if replaymessage[0] == "REPLAY" and Pstatus == 1:
                        # only do something if we get this while recording (otherwise ignored since it wouldn't make sense)
                        # which also means we should have filename and starttime defined
                        Pstatus = 2
                        checkininterval = checkinintervalnormal
                        StopRecording()
                        recordingendtime = time.time()
                        currentlyrecording = False
                        # Extract requested last few seconds
                        # playback with h264 is wonky, convert to mp4
                        recordinglength = recordingendtime - recordingstarttime
                        # To get slomo we take advantage that h264 has no clue about fps and set accordingly
                        # Problem is it messes with time calculations since I'm trying to trim just the last x seconds
                        # Need to scale times accordingly to desired playback speed
                        replaystarttime = max(0, recordinglength - float(replaymessage[1])) / float(replaymessage[3])
                        replayendtime = recordinglength / float(replaymessage[3])
                        replayduration = (replayendtime - replaystarttime)
                        convertstring = "MP4Box -fps " + str(thisframerate * float(replaymessage[3])) + " -splitx " + str(replaystarttime) + ":" + str(replayendtime) + " -add " + fileroot + ".h264 " + fileroot + ".mp4"
                        print(convertstring)
                        os.system(convertstring)
                        # Setup for replay
                        replaycount = 0
                        showings = int(replaymessage[2])
                        replayactive = False
                        # Estimate and pad playback time
                        playbackduration = replayduration + 3

                    if replaymessage[0] == "CANCEL":
                        if currentlyrecording:
                            # If actively recording, stop and reset status
                            StopRecording()
                            currentlyrecording = False
                            Pstatus = 0
                        # Regardless, revert checkin rate and disable any record triggers
                        checkininterval = checkinintervalnormal
                        #Also intercept any previously setup start recordings in this single response
                        readytostartrecording = False

            else:
                # server post had a failed contact
                print("FAILED CONTACT -", r.status_code)

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
            else:
                # start a playback (playback is false, but we're in playback status)
                omxc = Popen(['omxplayer', fileroot + ".mp4"])
                playbackstart = curTime
                replayactive = True
                
        elif readytostartrecording:
            # Start recording
            HideTheDesktop(True)
            fileroot = nextfileroot
            StartRecording(fileroot + ".h264", videonameroot)
            recordingstarttime = time.time()
            currentlyrecording = True
            Pstatus = 1
            # Reset the flag that triggered us to here
            readytostartrecording = False
            checkininterval = checkinintervalracing

        if Pstatus == 0:
            # Nothing going on - show the desktop
            HideTheDesktop(False)

finally:
    HideTheDesktop(False)
    if currentlyrecording:
        camera.stop_recording()
        camera.stop_preview()
    camera.close()
