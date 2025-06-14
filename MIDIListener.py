import mido
import time
import os
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
import sys

if sys.platform == 'win32':
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

MIDI_PORT_NAME = None
OUTPUT_DIR = "midi_captures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

NO_INPUT_TIMEOUT = 5 * 60
MIN_NOTES = 10
RECONNECT_INTERVAL = 2  # seconds between reconnection attempts

class MidiRecorder:
    def __init__(self):
        self.buffer = []
        self.last_input_time = time.time()
        self.note_on_count = 0
        self.log_output = []
        self.gui_open = False
        self.connected_port_name = None

        self.root = tk.Tk()
        self.root.withdraw()

    def log(self, text):
        print(text)
        self.log_output.append(text)

    def find_midi_input(self):
        """Find and return the first available MIDI input port"""
        if MIDI_PORT_NAME:
            inputs = mido.get_input_names()
            if MIDI_PORT_NAME in inputs:
                return MIDI_PORT_NAME
            else:
                return None
        else:
            inputs = mido.get_input_names()
            return inputs[0] if inputs else None

    def wait_for_midi_connection(self):
        """Wait for a MIDI device to connect"""
        self.log("Waiting for MIDI device to connect...")
        while True:
            port_name = self.find_midi_input()
            if port_name:
                self.log(f"MIDI device found: {port_name}")
                return port_name
            time.sleep(RECONNECT_INTERVAL)

    def open_midi_input(self):
        """Open MIDI input with error handling"""
        port_name = self.find_midi_input()
        if not port_name:
            port_name = self.wait_for_midi_connection()
        
        try:
            self.connected_port_name = port_name
            self.log(f"Connecting to MIDI input: {port_name}")
            return mido.open_input(port_name)
        except Exception as e:
            self.log(f"Failed to open MIDI port {port_name}: {e}")
            raise

    def is_port_still_available(self):
        """Check if the currently connected port is still available"""
        if not self.connected_port_name:
            return False
        
        available_ports = mido.get_input_names()
        return self.connected_port_name in available_ports

    def save_buffer_to_file(self, force=False):
        if self.note_on_count < MIN_NOTES and not force:
            self.log(f"Discarding file (only {self.note_on_count} notes).")
            self.buffer.clear()
            self.note_on_count = 0
            return

        if self.note_on_count <= 3:
            self.log(f"Discarding file (no notes pressed)")
            self.buffer.clear()
            self.note_on_count = 0
            return

        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        first_time = self.buffer[0][1] if self.buffer else 0
        last_time = first_time
        
        for msg, abs_time in self.buffer:
            delta_seconds = abs_time - last_time

            delta_ticks = mido.second2tick(delta_seconds, mid.ticks_per_beat, 600000)

            new_msg = msg.copy(time=int(delta_ticks))
            track.append(new_msg)
            
            last_time = abs_time

        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(OUTPUT_DIR, f"capture_{timestamp}.mid")
        mid.save(filename)
        self.log(f"Saved {filename} with {self.note_on_count} notes.")

        self.buffer.clear()
        self.note_on_count = 0

    def show_log_window(self):
        if self.gui_open:
            return
        self.gui_open = True

        def on_close():
            self.gui_open = False
            window.destroy()

        window = tk.Toplevel(self.root)
        window.title("MIDI Recorder Log")
        window.geometry("600x400+100+100")

        if sys.platform == 'win32':
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, -20)
            style |= 0x00000080
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, -20, style)

        text_area = ScrolledText(window, state='normal')
        text_area.pack(fill='both', expand=True)
        text_area.insert(tk.END, "\n".join(self.log_output))
        text_area.configure(state='disabled')

        window.protocol("WM_DELETE_WINDOW", on_close)

        window.focus_force()
        window.grab_set()
        window.wait_window()

    def run_with_reconnect(self):
        """Main loop with automatic reconnection handling"""
        port = None
        
        while True:
            try:
                # Open or reopen MIDI connection
                if port is None:
                    port = self.open_midi_input()
                    self.log("Connected! Listening for MIDI input...")
                
                # Main MIDI processing loop
                note36 = 0
                while True:
                    try:
                        # Check if port is still available
                        if not self.is_port_still_available():
                            self.log("MIDI device disconnected. Attempting to reconnect...")
                            port.close()
                            port = None
                            break
                        
                        # Process MIDI messages
                        for msg in port.iter_pending():
                            if not msg.is_realtime:
                                now = time.time()
                                self.buffer.append((msg, now))
                                self.last_input_time = now
                                if msg.type == 'note_on' and msg.velocity > 0:
                                    self.note_on_count += 1
                                    if msg.note == 36 and note36 >= 2:
                                        self.log("Note 36 pressed - saving buffer and showing log window.")
                                        self.save_buffer_to_file(force=True)
                                        self.root.after(0, self.show_log_window)
                                    elif msg.note == 36:
                                        note36 += 1
                                    else:
                                        note36 = 0
                                self.log(f"Got {msg}")

                        # Check for timeout
                        if self.buffer and (time.time() - self.last_input_time) > NO_INPUT_TIMEOUT:
                            self.log("No input timeout reached - saving buffer.")
                            self.save_buffer_to_file()

                        # Update GUI
                        self.root.update()
                        time.sleep(0.01)
                        
                    except Exception as e:
                        self.log(f"Error during MIDI processing: {e}")
                        if port:
                            try:
                                port.close()
                            except:
                                pass
                            port = None
                        break
                
            except Exception as e:
                self.log(f"Connection error: {e}")
                if port:
                    try:
                        port.close()
                    except:
                        pass
                    port = None
                
                # Wait before attempting to reconnect
                self.log(f"Waiting {RECONNECT_INTERVAL} seconds before reconnecting...")
                time.sleep(RECONNECT_INTERVAL)

    def run(self):
        """Legacy run method - now calls the reconnect version"""
        self.run_with_reconnect()

if __name__ == "__main__":
    recorder = None
    try:
        recorder = MidiRecorder()
        recorder.run()
    except KeyboardInterrupt:
        if recorder:
            recorder.save_buffer_to_file()
        print("Stopped by user.")
