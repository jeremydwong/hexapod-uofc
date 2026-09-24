==============================================================================
ForceSeatDI, copyright (C) 2012-2024 MotionSystems

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
=============================================================================

The latest version of documentation can be find at following address:
https://motionsystems.eu/ref/fsdi-related

Running on Linux:
-----------------

1. An application that uses ForceSeatDI with USB motion platform has to:
   a) have writing permission to device
   b) be able to detach device from the kernel.

   This is why it is recommended to RUN THE APPLICATION AS 'root'.

2. Binaries:
   * ForceSeatDI32.RSPi_3.so is armv7l 4.9.35.
   * ForceSeatDI64.RSPi_4_Bookworm.so is armv72 6.1.58.
   * ForceSeatDI64.RSPi_4_Bullseye.so is armv72 6.1.58.
   * ForceSeatDI64.LinuxPC.so is Generic Linux x64
   * ForceSeatDI32.LinuxPC.so is Generic Linux x86
   

3. When running on Raspberry Pi 3, make sure to rename:
     ForceSeatDI32.RSPi_3.so => ForceSeatDI32.so
	 
4. When running on Raspberry Pi 4 x64 BullsEye, make sure to rename:
     ForceSeatDI64.RSPi_4_Bullseye.so => ForceSeatDI64.so
	 
5. When running on Raspberry Pi 4 x64 Bookworm, make sure to rename:
     ForceSeatDI64.RSPi_4_Bookworm.so => ForceSeatDI64.so

6. When running on Generic Linux x86, make sure to rename:
     ForceSeatDI32.LinuxPC.so => ForceSeatDI32.so

7. When running on Generic Linux x64, make sure to rename:
     ForceSeatDI64.LinuxPC.so => ForceSeatDI64.so

8. Make sure to copy ForceSeatDI32.so and/or ForceSeatDI64.so to the same directory where your 
   executable is located. This applies also to examples.

9. Before you start your application, make sure that all dependencies are installed. You can use 
   following commands to verify dependencies:
     ldd ./ForceSeatDI32.so
     ldd ./ForceSeatDI64.so

10. libusb 1.0.x might be missing. You can install it using following command:
    sudo apt-get install libusb-1.0-0

11. For Python examples, Python 3.x is required (tested with Python 3.4.3)

12. Make sure that your application is compiled with -pthreads flag as internally 
    threads are used to speed up motion platform's work envelope calculation.

Linux troubleshooting:
-----------------------

ForceSeatDI races with kernel HID driver. By default the library tries to detach
the device from the kernel (this is why 'root' is required), but in case it fails, 
it might be required to do it manually (as 'root') before application is executed:
   sudo rmmod usbhid
   sudo modprobe usbhid quirks=0x0483:0xA110:0x04

Alternatively you can try to disable usbhid from loading:
a) edit or create:
    /etc/udev/rules.d/99-disable-usb-hid.rules 
b) add there following line:
    SUBSYSTEMS=="usb", DRIVERS=="usbhid", ACTION=="add", ATTR{authorized}="0"
c) restart udev
    sudo udevadm control --reload-rules && 
    sudo udevadm trigger
