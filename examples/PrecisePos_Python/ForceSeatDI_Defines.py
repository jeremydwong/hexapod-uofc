#
# Copyright (C) 2012-2026 MotionSystems
#
# This file is part of ForceSeatDI SDK.
#
# www.motionsystems.eu
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from ctypes import *

FSDI_UINT8  = c_uint8
FSDI_INT8   = c_int8
FSDI_UINT32 = c_uint32
FSDI_INT32  = c_int32
FSDI_UINT16 = c_uint16
FSDI_INT16  = c_int16
FSDI_FLOAT  = c_float
FSDI_UINT64 = c_uint64
FSDI_Bool   = c_char
FSDI_Char   = c_char

def FSDI_True():
    return FSDI_Bool(b'\x01')

def FSDI_False():
    return FSDI_Bool(b'\x00')

def FSDI_MotorsCount():
    return 6

def FSDI_SerialNumberBytesLength():
    return 12

def FSDI_SerialNumberStringLength():
    return 28
