import os
from os.path import isfile, join
import threading
import subprocess
import queue
import sys
import socket
import re
import tkinter
from tkinter.filedialog import askdirectory, askopenfilename, asksaveasfilename
import tkinter.ttk as ttk
import atexit
import winsound

def main():
  if not os.path.exists(os.path.dirname(os.path.abspath(__file__)) + "/config"):
      os.makedirs(os.path.dirname(os.path.abspath(__file__)) + "/config")

  #--- main functions ---
  def ffmpeg_out():
    while True:
      try:
        line = ffmpeg.stdout.readline()
        if line:
          print(line)
          
        if "frame=" in line or "Duration:" in line:
          output.put(line)
        if "Lsize" in line:
          return #exit thread
      except UnicodeDecodeError: #sometimes this error is thrown when reading ffmpeg stdout/working on better solution
        pass

  def start_ffmpeg(ffmpegSubprocess, subtitlestreamlist):
    global output
    global ffmpeg

    output = queue.Queue()

    finishLabel["text"] = ""
    finishLabel.update()

    filesToRender = 0
    for ffmpegCall in ffmpegSubprocess: #set up file progress label
      filesToRender = filesToRender + 1
    filesToRender = str(filesToRender)
    fileProgressCountLabel["text"] =  "0/" + filesToRender
    fileProgressCountLabel.update()
    
    overalltime = 0
    for ffmpegCall in ffmpegSubprocess: #calculate overall time of all videos
      ffprobe = subprocess.Popen(["FFmpeg/ffprobe.exe", ffmpegCall[2]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, creationflags=0x08000000)
      lines = ffprobe.stdout.readlines()
      for line in lines:
        if("Duration:" in line):
          match = re.search(r"[0-9]+:[0-9]+:[0-9]+\.[0-9]+", line)
          currenttime = match.group(0).split(":")
          hours = int(currenttime[0]) * 3600
          mins =  int(currenttime[1]) * 60
          secs = int(currenttime[2].split(".")[0])
          time = hours + mins + secs
          overalltime = overalltime + time

    env_vars = os.environ #copy environment variables
    env_vars["FC_CONFIG_DIR"] = os.path.dirname(os.path.abspath(__file__))
    env_vars["FONTCONFIG_FILE"] = "fonts.conf"
    env_vars["FONTCONFIG_PATH"] = os.path.dirname(os.path.abspath(__file__))
    #set program internal fonts.conf environment variables
    
    fontdir = os.path.dirname(os.path.abspath(__file__)) + "/fonts"
    if not os.path.exists(fontdir):
      os.makedirs(fontdir)
    
    lastmaxtime = 0
    i = 0
    filesProgress = 0
    ffmpegwait = False
    for ffmpegCall in ffmpegSubprocess: #start rendering loop
      
      if(ffmpegCall[len(ffmpegCall) - 3] == "-vf"): #extract all font files if any are available
        if(ffmpegwait):
          ffmpeg.wait() #wait until ffmpeg process is finished to release files in font dir

        fontfileList = os.listdir(fontdir)
        for fontfileName in fontfileList: #remove every file in font dir to not waste disk space
          os.remove(fontdir + "\\" + fontfileName)

        mkvextractFontsCall = ["MKVToolNix/mkvextract.exe", "attachments", ffmpegCall[2]]
        mkvmerge = subprocess.Popen(["MKVToolNix/mkvmerge.exe", "-i", ffmpegCall[2]], stdout=subprocess.PIPE, universal_newlines=True, creationflags=0x08000000)
        lines = mkvmerge.stdout.readlines()
        loop = 0
        for line in lines:
          if("Attachment ID" in line):
            loop += 1
            match = re.search(r"[a-zA-Z0-9-._ ]+\.[tTfFoOcC]{3}", line)
            mkvextractFontsCall.append(str(loop) + ":" + "fonts\\" + match.group(0))
            
        mkvextractFonts = subprocess.Popen(mkvextractFontsCall, stdout=subprocess.DEVNULL, creationflags=0x08000000)
        mkvextractFonts.wait()
        mkvextract = subprocess.Popen(["MKVToolNix/mkvextract.exe", "tracks", ffmpegCall[2], subtitlestreamlist[i] + ":subtitles.ass"], stdout=subprocess.DEVNULL, creationflags=0x08000000)
        mkvextract.wait()
        i = i + 1
        
      ffmpeg = subprocess.Popen(ffmpegCall, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, env=env_vars, creationflags=0x08000000) #start rendering with FFPMEG
      ffmpegwait = True
      
      ffmpeg_out_thread = threading.Thread(target=ffmpeg_out)
      ffmpeg_out_thread.setDaemon(True)
      ffmpeg_out_thread.start() #start FFMPEG listener
      
      firstloop = True
      loop = True
      while loop == True: #loop trough listener output and update progress bars
        lastline = output.get()
        match = re.search(r"[0-9]+:[0-9]+:[0-9]+\.[0-9]+", lastline)
        if(match != None):
          currenttime = match.group(0).split(":")
          hours = int(currenttime[0]) * 3600
          mins =  int(currenttime[1]) * 60
          secs = int(currenttime[2].split(".")[0])
          time = hours + mins + secs
          if(firstloop):
            videoduration = time
            firstloop = False
          else:
            percent = int(time / videoduration * 100)
            fileProgressbar["value"] = percent
            fileProgressbar.update()
              
            overallPercent = int((lastmaxtime + time) / overalltime * 100)
            completeProgressbar["value"] = overallPercent
            completeProgressbar.update()
              
            if(percent == 100):      
              loop = False
              
      filesProgress = filesProgress + 1
      fileProgressCountLabel["text"] =  str(filesProgress) + "/" + filesToRender
      fileProgressCountLabel.update()

      lastmaxtime = lastmaxtime + videoduration
      
    finishLabel["text"] = "Done!"
    finishLabel.update()
    renderButton.configure(state=tkinter.NORMAL)
    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
    return #exit thread
    
  def startRendering(): #prepare rendering
    renderButton.configure(state=tkinter.DISABLED)
    
    if(resolution.get() == "360p"):
      size = "640x360"
    elif(resolution.get()  == "480p"):
      size = "852x480"
    elif(resolution.get()  == "720p"):
      size = "1280x720"
    else:
      size = "1920x1080"

    if(vcodec.get() == "h264"):
      videocodec = "libx264"
    elif(vcodec.get() == "VP8"):
      videocodec = "libvpx"
    else:
      videocodec = "libvpx-vp9"

    if(acodec.get() == "aac"):
      audiocodec = "libvo_aacenc"
    elif(acodec.get() == "ac3"):
      audiocodec = "ac3"
    elif(acodec.get() == "mp3"):
      audiocodec = "mp3"
    elif(acodec.get() == "vorbis"):
      audiocodec = "libvorbis"
    else:
      audiocodec = "libopus"
    
    #set all option values
    options = dict()
    options["input"] = filepathInput.get()
    options["vcodec"] = videocodec
    #options["maxbitrate"] = maxBitrateInput.get()
    options["preset"] = presetText.get()
    options["crf"] = crfText.get()
    options["size"] = size
    options["abitrate"] = abitrate.get()  + "k"
    options["acodec"] = audiocodec
    options["subtitle"] = burnSubs.get()
    if(filepathOutput.get() == options["input"] or filepathOutput.get() == ""):
      options["output"] = options["input"] + "/rendered"
      if not os.path.exists(options["output"]):
        os.makedirs(options["output"])
    else:
      options["output"] = filepathOutput.get()
    
    ffmpegSubprocess = []
    subtitlestreamlist = []
    videoFiles = [fileListbox.get(idx) for idx in fileListbox.curselection()] #get all selected video files

    if(videoFiles): #loop trough video files
      for videoFile in videoFiles:
        filepath = options["input"] + "\\" + videoFile
        
        if(options["vcodec"] == "libvpx" or options["vcodec"] == "libvpx-vp9"):
          videocontainer = ".webm"
        else:
          videocontainer = ".mp4"
          
        outputfile = options["output"] + "\\" + videoFile.rsplit(".", 1)[0] + videocontainer
        
        subtitlestream = False
        ffprobe = subprocess.Popen(["FFmpeg/ffprobe.exe", filepath], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, creationflags=0x08000000)
        lines = ffprobe.stdout.readlines()
        for line in lines:
          if("Subtitle:" in line):
            match = re.search(r"#[0-9]+:[0-9]+", line)
            subtitlestream = match.group(0).split(":")[1]
            subtitlestreamlist.append(subtitlestream)

        ffmpegCall = ["FFmpeg/ffmpeg.exe"]
        ffmpegCall.append("-i")
        ffmpegCall.append(filepath)
        ffmpegCall.append("-vcodec")
        ffmpegCall.append(options["vcodec"])
        ffmpegCall.append("-preset")
        ffmpegCall.append(options["preset"])
        ffmpegCall.append("-crf")
        ffmpegCall.append(options["crf"])
        ffmpegCall.append("-qmin")
        ffmpegCall.append(options["crf"])
        ffmpegCall.append("-qmax")
        ffmpegCall.append(options["crf"])
        ffmpegCall.append("-threads")
        ffmpegCall.append("16")
        ffmpegCall.append("-s")
        ffmpegCall.append(options["size"])
        #if(options["maxbitrate"] != ""):
        # ffmpegCall.append("-maxrate")
        # ffmpegCall.append(options["maxbitrate"] + "k")
        # ffmpegCall.append("-bufsize")
        # ffmpegCall.append("6M")
        ffmpegCall.append("-acodec")
        ffmpegCall.append(options["acodec"])
        ffmpegCall.append("-b:a")
        ffmpegCall.append(options["abitrate"])
        ffmpegCall.append("-sn")
        if(options["subtitle"] == 1 or subtitlestream == True):
          ffmpegCall.append("-vf")
          ffmpegCall.append("ass=subtitles.ass")
        ffmpegCall.append("-y")
        ffmpegCall.append(outputfile)
        ffmpegSubprocess.append(ffmpegCall)

      start_ffmpeg_thread = threading.Thread(target=start_ffmpeg, args=(ffmpegSubprocess, subtitlestreamlist,))
      start_ffmpeg_thread.setDaemon(True)
      start_ffmpeg_thread.start() #start rendering thread
    else:
      renderButton.configure(state=tkinter.NORMAL)
  
  #--- GUI related functions ---
  def saveProfile():
    saveFile = asksaveasfilename(parent=mainWindow, defaultextension=".cfg", filetypes=[("configuration file", "*.cfg")], initialdir="/config")
    if(saveFile):
      file = open(saveFile, 'w+')
      file.write("%s\n%s\n%s\n%s\n%s\n%s\n%s\n%s" % ("pyrender conf:", vcodec.get(), str(presetScale.get()), str(crfScale.get()), resolution.get(), str(abitrate.get()),  str(acodec.get()), str(burnSubs.get())))
      file.close()

  def loadProfile():
    loadFile = askopenfilename(parent=mainWindow, defaultextension=".cfg", filetypes=[("configuration file", "*.cfg")], initialdir="/config")
    if(loadFile):
      file = open(loadFile, 'r')
      lines = file.read().splitlines()
      if(lines[0] == "pyrender conf:"):
        vcodec.set(lines[1])
        updateWindow(lines[1])
        presetScale.set(int(lines[2]))
        if(lines[2] == "0"):
          preset = "ultrafast"
        elif(lines[2] == "1"):
          preset = "superfast"
        elif(lines[2] == "2"):
          preset = "veryfast"
        elif(lines[2] == "3"):
          preset = "faster"
        elif(lines[2] == "4"):
          preset = "fast"
        elif(lines[2] == "5"):
          preset = "medium"
        elif(lines[2] == "6"):
          preset = "slow"
        elif(lines[2] == "7"):
          preset = "slower"
        else:
          preset = "veryslow"
        presetText.set(preset)
        
        crfScale.set(int(lines[3]))
        crfText.set(lines[3])
        
        resolution.set(lines[4])
        abitrate.set(lines[5])
        acodec.set(lines[6])
        burnSubs.set(lines[7])
        
      file.close()
    
  def choosePath(): #function to choose an input path
    choosePath = askdirectory(parent=mainWindow)
    if(choosePath):
      fileListbox.delete(0, tkinter.END)
      filepathInput.delete(0, tkinter.END)
      filepathInput.insert(0, choosePath)
      onlyfiles = [ f for f in os.listdir(choosePath) if isfile(join(choosePath,f)) ]
      for onlyfile in onlyfiles:
        fileext = onlyfile.rsplit(".", 1)
        if(len(fileext) == 2):
          fileext = fileext[1].lower()
          if fileext in ["avi", "flv", "h264", "h263", "h261", "m4v", "matroska", "webm", "mov", "mp4", "m4a", "3gp", "mp3", "mpg", "mpeg", "ogg", "vob", "wav", "webm_dash_manifest", "mkv", "wmv"]:
            fileListbox.insert(tkinter.END, onlyfile)

  def selectAll():
    fileListbox.select_set(0, tkinter.END)

  def deselectAll():
    fileListbox.select_clear(0, tkinter.END)
    
  def updateWindow(vcodec):
    if(vcodec == "h264"):
      presetScaleLabel.place(x=325, y=36)
      presetScale.place(x=370, y=36)
      presetScaleValueLabel.place(x=480, y=36)
      acodecMenu["menu"].delete(0, 'end')
      acodecMenu["menu"].add_command(label="aac", command=lambda: acodec.set("aac"))
      acodecMenu["menu"].add_command(label="ac3", command=lambda: acodec.set("ac3"))
      acodecMenu["menu"].add_command(label="mp3", command=lambda: acodec.set("mp3"))
      acodec.set("aac")
    else:
      presetScaleLabel.place_forget()
      presetScale.place_forget()
      presetScaleValueLabel.place_forget()
      acodecMenu["menu"].delete(0, 'end')
      acodecMenu["menu"].add_command(label="vorbis", command=lambda: acodec.set("vorbis"))
      acodecMenu["menu"].add_command(label="opus", command=lambda: acodec.set("opus"))
      acodec.set("vorbis")
      
  #def validateBitrate(input):
  # if(input.isdigit() or input == ""):
  #   return True
  # else:
  #   return False
  
  def updatePreset(presetValue): #resolve value to actual preset
    if(presetValue == "0"):
      preset = "ultrafast"
    elif(presetValue == "1"):
      preset = "superfast"
    elif(presetValue == "2"):
      preset = "veryfast"
    elif(presetValue == "3"):
      preset = "faster"
    elif(presetValue == "4"):
      preset = "fast"
    elif(presetValue == "5"):
      preset = "medium"
    elif(presetValue == "6"):
      preset = "slow"
    elif(presetValue == "7"):
      preset = "slower"
    else:
      preset = "veryslow"
    presetText.set(preset)

  def updateCrf(crfValue):
    crf = crfValue
    crfText.set(crf)
    
  def chooseOutPath(): #function to choose output directory path
    chooseOutPath = askdirectory(parent=mainWindow)
    filepathOutput.delete(0, tkinter.END)
    filepathOutput.insert(0, chooseOutPath)
  
  #--- build GUI ---
  mainWindow = tkinter.Tk() #create main windows object
  mainWindow.resizable(0,0) #make window non-resizeable
  mainWindow.iconbitmap("icon.ico") #set window icon (icon to change)
  mainWindow.title("PyRender 0.2.0") #set window title
  mainWindow.geometry("620x380") #set window dimensions
  
  menubar = tkinter.Menu(mainWindow, tearoff=0) #create toplevel menu
  filemenu = tkinter.Menu(menubar, tearoff=0)
  filemenu.add_command(label="Save profile", command=saveProfile)
  filemenu.add_command(label="Load profile", command=loadProfile)
  menubar.add_cascade(label="File", menu=filemenu)
  mainWindow.config(menu=menubar) #display the menu
  
  filepathInputLabel = tkinter.Label(mainWindow, text="Enter a file path with videos to convert:")
  filepathInputLabel.place(x=1, y=1) #set label
  
  filepathInput = tkinter.Entry(mainWindow) 
  filepathInput.place(width=232, height=23, x=1, y=20) #input for path
  
  pathButton = tkinter.Button(mainWindow, text="Choose path", command=choosePath) 
  pathButton.place(x=232, y=19) #button to open directory dialog

  scrollbar = tkinter.Scrollbar(mainWindow)
  scrollbar.place(height=230, x=293, y=60) #place scrollbar for fileListBox
  
  fileListbox = tkinter.Listbox(mainWindow, selectmode='multiple', yscrollcommand=scrollbar.set)
  fileListbox.place(width=292, height=230, x=1, y=60)
  scrollbar.config(command=fileListbox.yview) #place listbox for video files
  
  selectAllButton = tkinter.Button(mainWindow, text="Select all", command=selectAll)
  selectAllButton.place(x=1, y=291, width=154)
  
  deselectAllButton = tkinter.Button(mainWindow, text="Deselect all", command=deselectAll)
  deselectAllButton.place(x=156, y=291, width=154)
  
  renderButton = tkinter.Button(mainWindow, text="Start rendering", command=startRendering)
  renderButton.place(x=1, y=335, width=309) #button to start rendering
  
  VerticalSeparator = tkinter.Frame(mainWindow, bg="black")
  VerticalSeparator.place(x=311, height=362)
  
  vcodecLabel = tkinter.Label(mainWindow, text="video codec:")
  vcodecLabel.place(x=325, y=6)
  
  vcodec = tkinter.StringVar(mainWindow)
  vcodec.set("h264") #initial value
  vcodecMenu = tkinter.OptionMenu(mainWindow, vcodec, "h264", "VP8", "VP9", command=updateWindow)
  vcodecMenu.place(width=80, x=400, y=3)
  
  #maxBitrateLabel = tkinter.Label(mainWindow, text="| max bitrate:")
  #maxBitrateLabel.place(x=480, y=6)
  
  #maxBitrateInput = tkinter.Entry(mainWindow, validate="all", validatecommand=(mainWindow.register(validateBitrate), "%P")) 
  #maxBitrateInput.place(width=50, height=23, x=555, y=6) #input for path
  #maxBitrateInput.insert(0, "0")
  
  #maxBitrateInfo = tkinter.Label(mainWindow, text="(0 = unlimited)", font="TkTextFont 8")
  #maxBitrateInfo.place(x=543, y=26)
  
  presetScaleLabel = tkinter.Label(mainWindow, text="preset:")
  presetScaleLabel.place(x=325, y=36)
  
  presetScale = tkinter.Scale(mainWindow, orient=tkinter.HORIZONTAL, showvalue=0, from_=0, to=8, resolution=1, command=updatePreset)
  presetScale.place(x=370, y=36)
  presetScale.set(5) #place scale
  
  presetText = tkinter.StringVar()
  presetScaleValueLabel = tkinter.Label(mainWindow, text="medium", textvariable=presetText)
  presetScaleValueLabel.place(x=480, y=36)
  
  crfScaleLabel = tkinter.Label(mainWindow, text="crf:")
  crfScaleLabel.place(x=325, y=66)
  
  crfScale = tkinter.Scale(mainWindow, orient=tkinter.HORIZONTAL, showvalue=0, from_=0, to=63, resolution=1, command=updateCrf)
  crfScale.place(x=370, y=66)
  crfScale.set(23)
  
  crfText = tkinter.StringVar()
  crfScaleValueLabel = tkinter.Label(mainWindow, text="23", textvariable=crfText)
  crfScaleValueLabel.place(x=480, y=66)
  
  resLabel = tkinter.Label(mainWindow, text="resolution:")
  resLabel.place(x=325, y=96)
  
  resolution = tkinter.StringVar(mainWindow)
  resolution.set("720p") #initial value
  resolutionMenu = tkinter.OptionMenu(mainWindow, resolution, "360p", "480p", "720p", "1080p")
  resolutionMenu.place(width=80, x=400, y=93)
  
  acodecLabel = tkinter.Label(mainWindow, text="audio codec:")
  acodecLabel.place(x=325, y=126)
  
  acodec = tkinter.StringVar(mainWindow)
  acodec.set("aac") #initial value
  acodecMenu = tkinter.OptionMenu(mainWindow, acodec, "aac", "ac3", "mp3")
  acodecMenu.place(width=80, x=400, y=123)
  
  abitrateLabel = tkinter.Label(mainWindow, text="audio bitrate:")
  abitrateLabel.place(x=325, y=156)
  
  abitrate = tkinter.StringVar(mainWindow)
  abitrate.set("192") #initial value
  abitrateMenu = tkinter.OptionMenu(mainWindow, abitrate, "92", "128", "192", "256", "320")
  abitrateMenu.place(width=80, x=400, y=153)
  
  abitrateLabel = tkinter.Label(mainWindow, text="kbit/s")
  abitrateLabel.place(x=480, y=156)
  
  burnSubs = tkinter.IntVar()
  burnSubsCheck = tkinter.Checkbutton(mainWindow, text="Burn subtitles to video", variable=burnSubs)
  burnSubsCheck.place(x=320, y=185)
  
  HorizontialSeparator = tkinter.Frame(mainWindow, bg="black")
  HorizontialSeparator.place(x=311, y=210, width=311)
  
  filepathOutputLabel = tkinter.Label(mainWindow, text="Output directory:")
  filepathOutputLabel.place(x=325, y=215)
  
  filepathOutput = tkinter.Entry(mainWindow) 
  filepathOutput.place(width=210, height=23, x=325, y=235) #input field for output directory
  
  pathOutputButton = tkinter.Button(mainWindow, text="Choose path", command=chooseOutPath) 
  pathOutputButton.place(x=535, y=235) #button to open directory dialog
  
  fileProgressLabel = tkinter.Label(mainWindow, text="Progress of current file:")
  fileProgressLabel.place(x=325, y=260)
  
  fileProgressbar = ttk.Progressbar(orient=tkinter.HORIZONTAL, length=212, maximum=100, mode='determinate')
  fileProgressbar.place(x=325, y=280) #place progressbar
  
  fileProgressCountLabel = tkinter.Label(mainWindow, text="")
  fileProgressCountLabel.place(x=540, y=280)

  completeProgressLabel = tkinter.Label(mainWindow, text="Overall progress:")
  completeProgressLabel.place(x=325, y=305)
  
  completeProgressbar = ttk.Progressbar(orient=tkinter.HORIZONTAL, length=212, maximum=100, mode='determinate')
  completeProgressbar.place(x=325, y=325)
  
  finishLabel = tkinter.Label(mainWindow, text="", fg="dark green")
  finishLabel.place(x=540, y=325)
  
  mainWindow.mainloop()
  
  def exit_handler(): #terminate rendering process on exit
    try:
      ffmpeg.terminate()
    except (AttributeError, NameError):
      pass
  atexit.register(exit_handler)

if __name__ == "__main__":
  main()