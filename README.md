# i-forgot-to-record-my-piano
An application in Python that runs in the background and records MIDI input at all times. If you play something on your piano and forgot to record it, this app captures MIDI files (max. 5 min per file) so you will never lose your ideas, even if you forgot to record them. Press C2 3 times consecutively (note 36) to open the logs and also force save.

This is pretty robust and can handle the piano disconnecting and reconnecting, and runs even when a piano isn't connected at first (it will wait for one to connect)
Note: This only records on one device.

You can open the generated .mid files in applications like Cakewalk or Windows Media Player.

This code was created with the assistance of ChatGPT and Claude. It's free to use for everyone via Apache 2.0.


TO MAKE THIS RUN AT ALL TIMES (STARTUP APPS): Create a shortcut to `AutoMIDIListener.bat`, then go to `shell:startup` in the file explorer, and move the shortcut there. Click on the shortcut to activate it, and it will also activate every time you shut down/restart your computer.
