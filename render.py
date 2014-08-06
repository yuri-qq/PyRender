import os
import threading
import subprocess
import queue
from os.path import isfile, join
import sys
import re
import tkinter
from tkinter.filedialog import askdirectory
import tkinter.ttk as ttk
import atexit
ffmpeg = []
fileProgressbar= 0
output = 0
def main():
	global fileProgressbar
	
	currentdir = os.path.dirname(os.path.abspath(__file__))
	fontdir = currentdir + "\\fonts"
	options = dict.fromkeys(["input", "vcodec", "preset", "crf", "size", "abitrate", "acodec", "subtitle", "output"])
	
	if not os.path.exists(fontdir):
		os.makedirs(fontdir)

	mainWindow = tkinter.Tk() #create main windows object
	mainWindow.resizable(0,0)
	mainWindow.iconbitmap(currentdir + "\\icon.ico") #set window icon
	mainWindow.title("PyRender 0.1") #set window title
	mainWindow.geometry("620x360") #set window dimensions
	
	filepathInputLabel = tkinter.Label(mainWindow, text="Enter a file path with videos to convert:")
	filepathInputLabel.place(x=1, y=1) #set label
	
	filepathInput = tkinter.Entry(mainWindow) 
	filepathInput.place(width=232, height=23, x=1, y=20) #input field for path
	
	def choosePath(): #function to choose a path
		choosePath = askdirectory(parent=mainWindow)
		if(choosePath):
			fileListbox.delete(0, tkinter.END)
			filepathInput.delete(0, tkinter.END)
			filepathInput.insert(0, choosePath)
			onlyfiles = [ f for f in os.listdir(choosePath) if isfile(join(choosePath,f)) ]
			for onlyfile in onlyfiles:
				fileext = onlyfile.rsplit(".", 1)[1].lower()
				if fileext in ["avi", "flv", "h264", "h263", "h261", "m4v", "matroska", "webm", "mov", "mp4", "m4a", "3gp", "mp3", "mpg", "mpeg", "ogg", "vob", "wav", "webm_dash_manifest", "mkv", "wmv"]:
					fileListbox.insert(tkinter.END, onlyfile)
			
	pathButton = tkinter.Button(mainWindow, text="Choose path", command=choosePath) 
	pathButton.place(x=232, y=19) #button to open directory dialog

	scrollbar = tkinter.Scrollbar(mainWindow)
	scrollbar.place(height=230, x=293, y=60)
	
	fileListbox = tkinter.Listbox(mainWindow, selectmode='multiple', yscrollcommand=scrollbar.set)
	fileListbox.place(width=292, height=230, x=1, y=60)
	scrollbar.config(command=fileListbox.yview)
	
	def selectAll():
		fileListbox.select_set(0, tkinter.END)
	
	selectAllButton = tkinter.Button(mainWindow, text="Select all", command=selectAll)
	selectAllButton.place(x=1, y=291, width=154)
	
	def deselectAll():
		fileListbox.select_clear(0, tkinter.END)
	
	deselectAllButton = tkinter.Button(mainWindow, text="Deselect all", command=deselectAll)
	deselectAllButton.place(x=156, y=291, width=154)

	def ffmpeg_out():
		global ffmpeg
		global output
		while True:
			try:
				line = ffmpeg.stdout.readline()
				if line:
					output.put(line)
				else:
					return
			except UnicodeDecodeError:
				pass
	
	def start_ffmpeg(ffmpegSubprocess, subtitlestreamlist):
		global fileProgressbar
		global output
		global ffmpeg
		
		overalltime = 0
		for ffmpegCall in ffmpegSubprocess:
			ffprobe = subprocess.Popen(["ffprobe.exe", ffmpegCall[2]], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
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

		env_vars = os.environ
		env_vars["FC_CONFIG_DIR"] = os.path.dirname(os.path.abspath(__file__))
		env_vars["FONTCONFIG_FILE"] = "fonts.conf"
		env_vars["FONTCONFIG_PATH"] = os.path.dirname(os.path.abspath(__file__))
		lastmaxtime = 0
		i = 0
		for ffmpegCall in ffmpegSubprocess:
			if(ffmpegCall[15] == "-vf"):
				fontfileList = os.listdir(fontdir)
				for fontfileName in fontfileList:
					os.remove(fontdir + "\\" + fontfileName)

				mkvextractFontsCall = ["mkvextract.exe", "attachments", ffmpegCall[2]]
				mkvmerge = subprocess.Popen(["mkvmerge.exe", "-i", ffmpegCall[2]], stdout=subprocess.PIPE, universal_newlines=True)
				lines = mkvmerge.stdout.readlines()
				loop = 0
				for line in lines:
					if("Attachment ID" in line):
						loop += 1
						match = re.search(r"[a-zA-Z0-9-._ ]+\.[tTfFoOcC]{3}", line)
						mkvextractFontsCall.append(str(loop) + ":" + "fonts\\" + match.group(0))
						
				mkvextractFonts = subprocess.Popen(mkvextractFontsCall, stdout=subprocess.DEVNULL)
				mkvextractFonts.wait()
				mkvextract = subprocess.Popen(["mkvextract.exe", "tracks", ffmpegCall[2], subtitlestreamlist[i] + ":subtitles.ass"], stdout=subprocess.DEVNULL)
				mkvextract.wait()
				i = i + 1
				
			ffmpeg = subprocess.Popen(ffmpegCall, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, env=env_vars)
			ffmpeg_out_thread = threading.Thread(target=ffmpeg_out)
			ffmpeg_out_thread.setDaemon(True)
			ffmpeg_out_thread.start()
			
			firstloop = True
			loop = True
			while loop == True:
				try:
					lastline = output.get(True, 10)
					print(lastline)
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
							
							percent = int((lastmaxtime + time) / overalltime * 100)
							completeProgressbar["value"] = percent
							completeProgressbar.update()
				except queue.Empty:
					loop = False

			lastmaxtime = lastmaxtime + videoduration
		return
		
	def startRendering(): #start rendering
		global output
		renderButton.configure(state=tkinter.DISABLED)
		
		if(resolution.get() == "360p"):
			size = "640x360"
		elif(resolution.get()  == "480p"):
			size = "852x480"
		elif(resolution.get()  == "720p"):
			size = "1280x720"
		else:
			size = "1920x1080"
			
		if(acodec.get() == "aac"):
			audiocodec = "libvo_aacenc"
		elif(acodec.get() == "ac3"):
			audiocodec = "ac3"
		else:
			audiocodec = "mp3"
		
		options["input"] = filepathInput.get()
		options["vcodec"] = "libx264"
		options["preset"] = presetText.get()
		options["crf"] = crfText.get()
		options["size"] = size
		options["abitrate"] = abitrate.get()  + "k"
		options["acodec"] = audiocodec
		options["subtitle"] = burnSubs.get()
		options["output"] = filepathOutput.get()

		ffmpegSubprocess = []
		subtitlestreamlist = []
		videoFiles = [fileListbox.get(idx) for idx in fileListbox.curselection()]

		for videoFile in videoFiles:
			filepath = options["input"] + "\\" + videoFile
			outputfile = options["output"] + "\\" + videoFile.rsplit(".", 1)[0] + ".mp4"
			
			subtitlestream = False
			ffprobe = subprocess.Popen(["ffprobe.exe", filepath], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
			lines = ffprobe.stdout.readlines()
			for line in lines:
				if("Subtitle:" in line):
					match = re.search(r"#[0-9]+:[0-9]+", line)
					subtitlestream = match.group(0).split(":")[1]
					subtitlestreamlist.append(subtitlestream)
			
			if(options["subtitle"] == 0 or subtitlestream == False):
				ffmpegCall = [currentdir + "\\ffmpeg.exe", "-i", filepath, "-vcodec", options["vcodec"], "-preset", options["preset"], "-crf", options["crf"], "-s", options["size"], "-acodec", options["acodec"], "-b:a", options["abitrate"], "-y", outputfile]
				ffmpegSubprocess.append(ffmpegCall)
			else:
				ffmpegCall = [currentdir + "\\ffmpeg.exe", "-i", filepath, "-vcodec", options["vcodec"], "-preset", options["preset"], "-crf", options["crf"], "-s", options["size"], "-acodec", options["acodec"], "-b:a", options["abitrate"], "-vf", "ass=subtitles.ass", "-y", outputfile]
				ffmpegSubprocess.append(ffmpegCall)

		output = queue.Queue()
		start_ffmpeg_thread = threading.Thread(target=start_ffmpeg, args=(ffmpegSubprocess, subtitlestreamlist,))
		start_ffmpeg_thread.setDaemon(True)
		start_ffmpeg_thread.start()
		renderButton.configure(state=tkinter.NORMAL)
	
	renderButton = tkinter.Button(mainWindow, text="Start rendering", command=startRendering)
	renderButton.place(x=1, y=335, width=309) #button to start rendering
	
	VerticalSeparator = tkinter.Frame(mainWindow, bg="black")
	VerticalSeparator.place(x=311, height=362)
	
	vcodecLabel = tkinter.Label(mainWindow, text="video codec:         h264")
	vcodecLabel.place(x=325, y=6) #set label
	
	presetScaleLabel = tkinter.Label(mainWindow, text="preset:")
	presetScaleLabel.place(x=325, y=36) #set label
	
	presetText = tkinter.StringVar()
	def updatePreset(presetValue):
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
	
	presetScale = tkinter.Scale(mainWindow, orient=tkinter.HORIZONTAL, showvalue=0, from_=0, to=8, resolution=1, command=updatePreset)
	presetScale.place(x=370, y=36)
	presetScale.set(5)
	
	presetScaleValueLabel = tkinter.Label(mainWindow, text="medium", textvariable=presetText)
	presetScaleValueLabel.place(x=480, y=36) #set label
	
	crfScaleLabel = tkinter.Label(mainWindow, text="crf:")
	crfScaleLabel.place(x=325, y=66) #set label
	
	crfText = tkinter.StringVar()
	def updateCrf(crfValue):
		crf = crfValue
		crfText.set(crf)
	
	crfScale = tkinter.Scale(mainWindow, orient=tkinter.HORIZONTAL, showvalue=0, from_=17, to=29, resolution=1, command=updateCrf)
	crfScale.place(x=370, y=66)
	crfScale.set(23)
	
	crfScaleValueLabel = tkinter.Label(mainWindow, text="23", textvariable=crfText)
	crfScaleValueLabel.place(x=480, y=66) #set label
	
	resLabel = tkinter.Label(mainWindow, text="resolution:")
	resLabel.place(x=325, y=96) #set label
	
	resolution = tkinter.StringVar(mainWindow)
	resolution.set("720p") # initial value
	resolutionMenu = tkinter.OptionMenu(mainWindow, resolution, "360p", "480p", "720p", "1080p")
	resolutionMenu.place(width=80, x=400, y=93)
	
	acodecLabel = tkinter.Label(mainWindow, text="audio codec:")
	acodecLabel.place(x=325, y=126) #set label
	
	acodec = tkinter.StringVar(mainWindow)
	acodec.set("aac") # initial value
	acodecMenu = tkinter.OptionMenu(mainWindow, acodec, "aac", "ac3", "mp3")
	acodecMenu.place(width=80, x=400, y=123)
	
	abitrateLabel = tkinter.Label(mainWindow, text="audio bitrate:")
	abitrateLabel.place(x=325, y=156) #set label
	
	abitrate = tkinter.StringVar(mainWindow)
	abitrate.set("192") # initial value
	abitrateMenu = tkinter.OptionMenu(mainWindow, abitrate, "92", "128", "192", "256", "320")
	abitrateMenu.place(width=80, x=400, y=153)
	
	abitrateLabel = tkinter.Label(mainWindow, text="kbit/s")
	abitrateLabel.place(x=480, y=156) #set label
	
	burnSubs = tkinter.IntVar()
	burnSubsCheck = tkinter.Checkbutton(mainWindow, text="Burn subtitles to video", variable=burnSubs)
	burnSubsCheck.place(x=320, y=185)
	
	HorizontialSeparator = tkinter.Frame(mainWindow, bg="black")
	HorizontialSeparator.place(x=311, y=210, width=311)
	
	filepathOutputLabel = tkinter.Label(mainWindow, text="output:")
	filepathOutputLabel.place(x=325, y=215) #set label
	
	filepathOutput = tkinter.Entry(mainWindow) 
	filepathOutput.place(width=232, height=23, x=325, y=235) #input field for path
	
	def chooseOutPath(): #function to choose a path
		chooseOutPath = askdirectory(parent=mainWindow)
		filepathOutput.delete(0, tkinter.END)
		filepathOutput.insert(0, chooseOutPath)
	
	pathOutputButton = tkinter.Button(mainWindow, text="Choose path", command=chooseOutPath) 
	pathOutputButton.place(x=535, y=235) #button to open directory dialog
	
	fileProgressLabel = tkinter.Label(mainWindow, text="Progress of current file:")
	fileProgressLabel.place(x=325, y=260) #set label
	
	fileProgress = tkinter.IntVar()
	fileProgressbar = ttk.Progressbar(orient=tkinter.HORIZONTAL, length=212, maximum=100, mode='determinate')
	fileProgressbar.place(x=325, y=280)

	completeProgressLabel = tkinter.Label(mainWindow, text="Overall progress:")
	completeProgressLabel.place(x=325, y=305) #set label
	
	completeProgressbar = ttk.Progressbar(orient=tkinter.HORIZONTAL, length=212, maximum=100, mode='determinate')
	completeProgressbar.place(x=325, y=325)
	
	mainWindow.mainloop()
	
	def exit_handler():
		global ffmpeg
		try:
			ffmpeg.terminate()
		except AttributeError:
			pass
	atexit.register(exit_handler)

if __name__ == "__main__":
	main()