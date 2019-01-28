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
# function for stopping recording
def StopRecording():
    camera.remove_overlay(overlayleft)
    camera.remove_overlay(overlayright)
    camera.stop_recording()
    camera.stop_preview()

# function for toggling the screen to be blanked or not - here due to repeated use      
def HideTheDesktop(hideIt = True):
    if hideIt:
        #set blank screen behind everything
        pygame.display.init()
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

# setup states for tracking
currentlyrecording = False
readytostartrecording = False

# Setup lists - Python lists aren't easy to make on the fly and we know what they will be
raceinfo = ["Den", "Race", "Heat", "Total Heats"]
racerinfo = [ ["Name", "Car", "Number", "Lane", "Photo Location"], ["Name", "Car", "Number", "Lane", "Photo Location"], ["Name", "Car", "Number", "Lane", "Photo Location"] ]
racerphotosloc = ["one", "two", "three"]

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
                # Reset replayfin after good POST to only send one scan of 1
                PreplayFin = 0
                lastcheckin = curTime

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

            camera.start_recording(fileroot, format='h264', intra_period = 10)
            camera.start_preview()
            recordingstarttime = time.time()
            currentlyrecording = True
            Pstatus = 1
            # Reset the flag that triggered us to here
            readytostartrecording = False

            #Ask for race info for overlay
            racerparams = {'query':"poll.now-racing", 'row-height':"150"}
            Rraceinfo = requests.get(url = replayurl, params = racerparams)
            #Check we got a valid response
            if Rraceinfo.status_code == requests.codes.ok:
                #Look for the data
                tree = ElementTree.fromstring(Rraceinfo.content)
                for currentheat in tree.iter("current-heat"):
                    raceinfo = [currentheat.text, currentheat.attrib["round"], currentheat.attrib["heat"], currentheat.attrib["number-of-heats"] ]
                for racer in tree.iter("racer"):
                    racerindex = int(racer.attrib["lane"]) - 1
                    racerinfo[racerindex] = [racer.attrib["name"], racer.attrib["carname"], racer.attrib["carnumber"], racer.attrib["lane"], racer.attrib["photo"] ]

                #Get the photos
                racerphotosloc = [racerinfo[0][4], racerinfo[1][4], racerinfo[2][4] ]
                for num, photoloc in enumerate(racerphotosloc, start=1):
                    imgurl = derbynetserverIP + "/" + photoloc
                    imgresponse = requests.get(imgurl)
                    if imgresponse.status_code == requests.codes.ok:
                        racerimgname = "racer" + str(num) + ".jpg"
                        with open(directory + racerimgname, 'wb') as f:
                            f.write(imgresponse.content)

                #Setup overlays and show them
                namePad = Image.new('RGB', (1280, 64))
                namePadImage = textPad.copy()
                
                racer1img = Image.open(directory + 'racer1.jpg')
                racer2img = Image.open(directory + 'racer2.jpg')
                racer3img = Image.open(directory + 'racer3.jpg')

                racer1pad = Image.new('RGB', (
                 ((racer1img.size[0] + 31) // 32) * 32,
                 ((racer1img.size[1] + 15) // 16) * 16,
                 ))
                racer2pad = Image.new('RGB', (
                 ((racer2img.size[0] + 31) // 32) * 32,
                 ((racer2img.size[1] + 15) // 16) * 16,
                 ))
                racer3pad = Image.new('RGB', (
                 ((racer3img.size[0] + 31) // 32) * 32,
                 ((racer3img.size[1] + 15) // 16) * 16,
                 ))

                racer1pad.paste(racer1img, (0, 0))
                racer2pad.paste(racer2img, (0, 0))
                racer3pad.paste(racer3img, (0, 0))

                # Layer 3 Left Bar info
                textPadImageLeft = textPad.copy()
                drawTextImage = ImageDraw.Draw(textPadImageLeft)
                drawTextImage.text((20, 20),raceinfo[0] , font=fontBold, fill=("Red"))
                overlayleft = camera.add_overlay(textPadImageLeft.tobytes(), size=(224, 960), alpha = 255, layer = 3, fullscreen = False, window = (0,0,224, 960))

                # Layer 3 Right Bar info
                textPadImageRight = textPad.copy()
                drawTextImage = ImageDraw.Draw(textPadImageRight)
                drawTextImage.text((20, 20),"Race " + raceinfo[1], font=fontBold, fill=("Yellow"))
                drawTextImage.text((20, 200),"Heat " + raceinfo[2] + " of " + raceinfo[3], font=fontBold, fill=("Yellow"))
                overlayright = camera.add_overlay(textPadImageRight.tobytes(), size=(224, 960), alpha = 255, layer = 3, fullscreen = False, window = (1696,0,224,960))
                
                # Layer 4 racer name bar overlay
                overlay = camera.add_overlay(namePadImage.tobytes(), size=(1280, 64), alpha = 128, layer = 4, fullscreen = False, window = (0,700,1280,64))
                namePadImage = namePad.copy()
                drawnameImage = ImageDraw.Draw(namePadImage)
                drawnameImage.text((50, 18),racerinfo[0][0] , font=fontBold, fill=("Yellow"))
                drawnameImage.text((300, 18),racerinfo[1][0] , font=fontBold, fill=("Yellow"))
                drawnameImage.text((550, 18),racerinfo[2][0] , font=fontBold, fill=("Yellow"))
                overlay.update(namePadImage.tobytes())

                # Layer 4 racer pic bar overlay
                overlay = camera.add_overlay(racer1pad.tobytes(), size=racer1img.size, alpha = 255, layer = 4, fullscreen = False, window = (200,200,446,299))
                overlay = camera.add_overlay(racer2pad.tobytes(), size=racer2img.size, alpha = 255, layer = 4, fullscreen = False, window = (800,200,446,299))
                overlay = camera.add_overlay(racer3pad.tobytes(), size=racer3img.size, alpha = 255, layer = 4, fullscreen = False, window = (1400,200,446,299))

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
