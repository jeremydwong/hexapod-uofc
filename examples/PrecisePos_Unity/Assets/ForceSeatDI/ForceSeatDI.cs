/*
 * Copyright (C) 2012-2026 MotionSystems
 * 
 * This file is part of ForceSeatDI SDK.
 *
 * www.motionsystems.eu
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
*/

using Microsoft.Win32;
using System;
using System.Runtime.InteropServices;

namespace MotionSystems
{
	///
	/// Wrapper for ForceSeatDI native DLL
	///
	public class ForceSeatDI: IDisposable
	{
		public ForceSeatDI(string searchingPath = null)
		{
			LoadAndCreate(searchingPath);
		}

		public void Dispose()
		{
			Close();
		}

		public bool IsLoaded()
		{
			return m_api != IntPtr.Zero;
		}

		///
		/// Connect to USB device with given name and serial number.
		/// 
		public bool ConnectToUsbDevice(string name, string serialNumber)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiConnectToUsbDevice(m_api, name, serialNumber) != 0;
		}

		///
		/// Connect to network device that has associated specified IP address.
		///
		public bool ConnectToNetworkDevice(string ipAddress)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiConnectToNetworkDevice(m_api, ipAddress) != 0;
		}

		///
		/// Check if the motion platform is connected
		///
		public bool TestConnection(ref bool isConnected)
		{
			if (m_api == IntPtr.Zero) return false;
			byte isConnectedByte = 0;
			if (m_fsdiTestConnection(m_api, ref isConnectedByte) != 0)
			{
				isConnected = isConnectedByte != 0;
				return true;
			}
			return false;
		}

		///
		/// Request moving to 'park' position. It might now work when motion platform is in paused mode.
		///
		public bool Park(FSDI_ParkMode parkMode)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiPark(m_api, (byte)parkMode) != 0;
		}

		///
		/// Call this function everytime when you want to change position of motion platform's top table (top frame)
		///
		public bool SendTopTablePosPhy(ref FSDI_TopTablePositionPhysical position)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiSendTopTablePosPhy(m_api, ref position) != 0;
		}

		///
		/// Call this function everytime when you want to change position of motion platform's top table (top frame)
		///
		public bool SendTopTablePosPhy2(ref FSDI_TopTablePositionPhysical position, ref FSDI_SFX sfx)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiSendTopTablePosPhy2(m_api, ref position, ref sfx) != 0;
		}

		///
		/// Call this function everytime when you want to change position of motion platform's top table (top frame)
		///
		public bool SendTopTableMatrixPhy(ref FSDI_TopTableMatrixPhysical matrix)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiSendTopTableMatrixPhy(m_api, ref matrix) != 0;
		}

		///
		/// Call this function everytime when you want to change position of motion platform's top table (top frame)
		///
		public bool SendTopTableMatrixPhy2(ref FSDI_TopTableMatrixPhysical matrix, ref FSDI_SFX sfx)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiSendTopTableMatrixPhy2(m_api, ref matrix, ref sfx) != 0;
		}

		///
		/// Call this function everytime when you want to change position of actuators arms
		///
		public bool SendActuatorsPosLog(ref FSDI_RequiredActuatorsPositionLogical position)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiSendActuatorsPosLog(m_api, ref position) != 0;
		}

		///
		/// Call this function everytime when you want to change position of actuators arms
		///
		public bool SendActuatorsPosLog2(ref FSDI_RequiredActuatorsPositionLogical position, ref FSDI_SFX sfx)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiSendActuatorsPosLog2(m_api, ref position, ref sfx) != 0;
		}

		///
		/// Call this function to get current platform status and actuators position
		///
		public bool GetPlatformInfo(ref FSDI_PlatformInfo platformInfo)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiGetPlatformInfo(m_api, ref platformInfo) != 0;
		}

		///
		/// Call this function to get current actuators position
		///
		public bool GetActuatorsPosLog(ref FSDI_ActualActuatorsPositionLogical position)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiGetActuatorsPosLog(m_api, ref position) != 0;
		}

		///
		/// Read serial number from the motion platform
		///
		public bool GetSerialNumber(ref string serialNumber)
		{
			if (m_api == IntPtr.Zero) return false;

			FSDI_PlatformInfo platformInfo = new FSDI_PlatformInfo();
			platformInfo.structSize = (byte)Marshal.SizeOf(platformInfo);

			if (m_fsdiGetPlatformInfo(m_api, ref platformInfo) != 0)
			{
				string sn = "";
				sn += platformInfo.serialNumber1.ToString("X2");
				sn += platformInfo.serialNumber2.ToString("X2");
				sn += platformInfo.serialNumber3.ToString("X2");
				sn += '-';
				sn += platformInfo.serialNumber4.ToString("X2");
				sn += platformInfo.serialNumber5.ToString("X2");
				sn += platformInfo.serialNumber6.ToString("X2");
				sn += '-';
				sn += platformInfo.serialNumber7.ToString("X2");
				sn += platformInfo.serialNumber8.ToString("X2");
				sn += platformInfo.serialNumber9.ToString("X2");
				sn += '-';
				sn += platformInfo.serialNumber10.ToString("X2");
				sn += platformInfo.serialNumber11.ToString("X2");
				sn += platformInfo.serialNumber12.ToString("X2");

				serialNumber = sn;
				return true;
			}
			return false;
		}

		///
		/// Check if license is valid:
		/// 1. If function returns 'false', then there is no connection to the motion platform. isValid is ignored.
		/// 2. If function returns 'true', then isValid contains information about license status.
		///
		public bool GetLicenseStatus(ref bool isValid)
		{
			if (m_api == IntPtr.Zero) return false;
			byte isValidByte = 0;
			if (m_fsdiGetLicenseStatus(m_api, ref isValidByte) != 0)
			{
				isValid = isValidByte != 0;
				return true;
			}
			return false;
		}

		///
		/// Call this function to get actual top table (top frame) position in real world units
		///
		public bool GetTopTablePosPhy(ref FSDI_ActualTopTablePositionPhysical position)
		{
			if (m_api == IntPtr.Zero) return false;
			return m_fsdiGetTopTablePosPhy(m_api, ref position) != 0;
		}

		#region Internals
		private IntPtr m_api = IntPtr.Zero;
		private IntPtr m_apiDll = IntPtr.Zero;

		~ForceSeatDI()
		{
			// Just in case it is not deleted
			Close();
		}

		private Delegate LoadFunction<T>(string functionName)
		{
			var addr = GetProcAddress(m_apiDll, functionName);
			if (addr == IntPtr.Zero) 
			{
				return null;
			}
			return Marshal.GetDelegateForFunctionPointer(addr, typeof(T));
		}

		private void LoadAndCreate(string searchingPath)
		{
			bool is64Bits = IntPtr.Size > 4;
			
			string dllName = is64Bits 
				? "ForceSeatDI64.dll" 
				: "ForceSeatDI32.dll";

			// Check searching path
			if (m_apiDll == IntPtr.Zero && searchingPath != null)
			{
				m_apiDll = LoadLibrary(searchingPath + "\\" + dllName);
			}

			// If there is still not ForceSeatDIxx.dll found, then let's try in standard search path
			if (m_apiDll == IntPtr.Zero)
			{
				m_apiDll = LoadLibrary(dllName);
			}

			if (m_apiDll != IntPtr.Zero) 
			{
				m_fsdiCreate                 = (ForceSeatDI_Create_Delegate)                 LoadFunction<ForceSeatDI_Create_Delegate>                ("ForceSeatDI_Create");
				m_fsdiDelete                 = (ForceSeatDI_Delete_Delegate)                 LoadFunction<ForceSeatDI_Delete_Delegate>                ("ForceSeatDI_Delete");
				m_fsdiConnectToUsbDevice     = (ForceSeatDI_ConnectToUsbDevice_Delegate)     LoadFunction<ForceSeatDI_ConnectToUsbDevice_Delegate>    ("ForceSeatDI_ConnectToUsbDevice");
				m_fsdiConnectToNetworkDevice = (ForceSeatDI_ConnectToNetworkDevice_Delegate) LoadFunction<ForceSeatDI_ConnectToNetworkDevice_Delegate>("ForceSeatDI_ConnectToNetworkDevice");
				m_fsdiTestConnection         = (ForceSeatDI_TestConnection_Delegate)         LoadFunction<ForceSeatDI_TestConnection_Delegate>        ("ForceSeatDI_TestConnection");
				m_fsdiPark                   = (ForceSeatDI_Park_Delegate)                   LoadFunction<ForceSeatDI_Park_Delegate>                  ("ForceSeatDI_Park");
				m_fsdiSendTopTablePosPhy     = (ForceSeatDI_SendTopTablePosPhy_Delegate)     LoadFunction<ForceSeatDI_SendTopTablePosPhy_Delegate>    ("ForceSeatDI_SendTopTablePosPhy");
				m_fsdiSendTopTablePosPhy2    = (ForceSeatDI_SendTopTablePosPhy2_Delegate)    LoadFunction<ForceSeatDI_SendTopTablePosPhy2_Delegate>   ("ForceSeatDI_SendTopTablePosPhy2");
				m_fsdiSendTopTableMatrixPhy  = (ForceSeatDI_SendTopTableMatrixPhy_Delegate)  LoadFunction<ForceSeatDI_SendTopTableMatrixPhy_Delegate> ("ForceSeatDI_SendTopTableMatrixPhy");
				m_fsdiSendTopTableMatrixPhy2 = (ForceSeatDI_SendTopTableMatrixPhy2_Delegate) LoadFunction<ForceSeatDI_SendTopTableMatrixPhy2_Delegate>("ForceSeatDI_SendTopTableMatrixPhy2");
				m_fsdiSendActuatorsPosLog    = (ForceSeatDI_SendActuatorsPosLog_Delegate)    LoadFunction<ForceSeatDI_SendActuatorsPosLog_Delegate>   ("ForceSeatDI_SendActuatorsPosLog");
				m_fsdiSendActuatorsPosLog2   = (ForceSeatDI_SendActuatorsPosLog2_Delegate)   LoadFunction<ForceSeatDI_SendActuatorsPosLog2_Delegate>  ("ForceSeatDI_SendActuatorsPosLog2");
				m_fsdiGetPlatformInfo        = (ForceSeatDI_GetPlatformInfo_Delegate)        LoadFunction<ForceSeatDI_GetPlatformInfo_Delegate>       ("ForceSeatDI_GetPlatformInfo");
				m_fsdiGetActuatorsPosLog     = (ForceSeatDI_GetActuatorsPosLog_Delegate)     LoadFunction<ForceSeatDI_GetActuatorsPosLog_Delegate>    ("ForceSeatDI_GetActuatorsPosLog");
				m_fsdiGetLicenseStatus       = (ForceSeatDI_GetLicenseStatus_Delegate)       LoadFunction<ForceSeatDI_GetLicenseStatus_Delegate>      ("ForceSeatDI_GetLicenseStatus");
				m_fsdiGetTopTablePosPhy      = (ForceSeatDI_GetTopTablePosPhy_Delegate)      LoadFunction<ForceSeatDI_GetTopTablePosPhy_Delegate>     ("ForceSeatDI_GetTopTablePosPhy");


				if (m_fsdiCreate                 != null &&
					m_fsdiDelete                 != null &&
					m_fsdiConnectToUsbDevice     != null &&
					m_fsdiConnectToNetworkDevice != null &&
					m_fsdiTestConnection         != null &&
					m_fsdiPark                   != null &&
					m_fsdiSendTopTablePosPhy     != null &&
					m_fsdiSendTopTablePosPhy2    != null &&
					m_fsdiSendTopTableMatrixPhy  != null &&
					m_fsdiSendTopTableMatrixPhy2 != null &&
					m_fsdiSendActuatorsPosLog    != null &&
					m_fsdiSendActuatorsPosLog2   != null &&
					m_fsdiGetPlatformInfo        != null &&
					m_fsdiGetActuatorsPosLog     != null &&
					m_fsdiGetLicenseStatus       != null &&
					m_fsdiGetTopTablePosPhy      != null)
				{
					m_api = m_fsdiCreate();
				}
			}
		}

		private void Close()
		{
			if (m_api != IntPtr.Zero)
			{
				m_fsdiDelete(m_api);
				m_api = IntPtr.Zero;
			}

			m_fsdiCreate                 = null;
			m_fsdiDelete                 = null;
			m_fsdiConnectToUsbDevice     = null;
			m_fsdiConnectToNetworkDevice = null;
			m_fsdiTestConnection         = null;
			m_fsdiPark                   = null;
			m_fsdiSendTopTablePosPhy     = null;
			m_fsdiSendTopTablePosPhy2    = null;
			m_fsdiSendTopTableMatrixPhy  = null;
			m_fsdiSendTopTableMatrixPhy2 = null;
			m_fsdiSendActuatorsPosLog    = null;
			m_fsdiSendActuatorsPosLog2   = null;
			m_fsdiGetPlatformInfo        = null;
			m_fsdiGetActuatorsPosLog     = null;
			m_fsdiGetLicenseStatus       = null;
			m_fsdiGetTopTablePosPhy      = null;

			if (m_apiDll != IntPtr.Zero)
			{
				FreeLibrary(m_apiDll);
				m_apiDll = IntPtr.Zero;
			}
		}
		#endregion

		#region DLLImports
		[DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
		private static extern IntPtr LoadLibrary(string libname);

		[DllImport("kernel32.dll", CharSet = CharSet.Auto)]
		private static extern bool FreeLibrary(IntPtr hModule);

		[DllImport("Kernel32.dll", CharSet = CharSet.Ansi, ExactSpelling = true, SetLastError = true)]
		private static extern IntPtr GetProcAddress(IntPtr hModule, string procName);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate IntPtr ForceSeatDI_Create_Delegate                ();

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate void   ForceSeatDI_Delete_Delegate                (IntPtr api);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_ConnectToUsbDevice_Delegate    (IntPtr api, string name, string serialNumber);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_ConnectToNetworkDevice_Delegate(IntPtr api, string ipAddress);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_TestConnection_Delegate        (IntPtr api, ref byte isConnected);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_Park_Delegate                  (IntPtr api, byte parkMode);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_SendTopTablePosPhy_Delegate    (IntPtr api, ref FSDI_TopTablePositionPhysical position);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_SendTopTablePosPhy2_Delegate   (IntPtr api, ref FSDI_TopTablePositionPhysical position, ref FSDI_SFX sfx);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_SendTopTableMatrixPhy_Delegate (IntPtr api, ref FSDI_TopTableMatrixPhysical matrix);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_SendTopTableMatrixPhy2_Delegate(IntPtr api, ref FSDI_TopTableMatrixPhysical matrix, ref FSDI_SFX sfx);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_SendActuatorsPosLog_Delegate   (IntPtr api, ref FSDI_RequiredActuatorsPositionLogical position);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_SendActuatorsPosLog2_Delegate  (IntPtr api, ref FSDI_RequiredActuatorsPositionLogical position, ref FSDI_SFX sfx);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_GetPlatformInfo_Delegate       (IntPtr api, ref FSDI_PlatformInfo platformInfo);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_GetActuatorsPosLog_Delegate    (IntPtr api, ref FSDI_ActualActuatorsPositionLogical position);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_GetLicenseStatus_Delegate      (IntPtr api, ref byte isValid);

		[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
		private delegate byte   ForceSeatDI_GetTopTablePosPhy_Delegate     (IntPtr api, ref FSDI_ActualTopTablePositionPhysical position);

		private ForceSeatDI_Create_Delegate                 m_fsdiCreate;
		private ForceSeatDI_Delete_Delegate                 m_fsdiDelete;
		private ForceSeatDI_ConnectToUsbDevice_Delegate     m_fsdiConnectToUsbDevice;
		private ForceSeatDI_ConnectToNetworkDevice_Delegate m_fsdiConnectToNetworkDevice;
		private ForceSeatDI_TestConnection_Delegate         m_fsdiTestConnection;
		private ForceSeatDI_Park_Delegate                   m_fsdiPark;
		private ForceSeatDI_SendTopTablePosPhy_Delegate     m_fsdiSendTopTablePosPhy;
		private ForceSeatDI_SendTopTablePosPhy2_Delegate    m_fsdiSendTopTablePosPhy2;
		private ForceSeatDI_SendTopTableMatrixPhy_Delegate  m_fsdiSendTopTableMatrixPhy;
		private ForceSeatDI_SendTopTableMatrixPhy2_Delegate m_fsdiSendTopTableMatrixPhy2;
		private ForceSeatDI_SendActuatorsPosLog_Delegate    m_fsdiSendActuatorsPosLog;
		private ForceSeatDI_SendActuatorsPosLog2_Delegate   m_fsdiSendActuatorsPosLog2;
		private ForceSeatDI_GetPlatformInfo_Delegate        m_fsdiGetPlatformInfo;
		private ForceSeatDI_GetActuatorsPosLog_Delegate     m_fsdiGetActuatorsPosLog;
		private ForceSeatDI_GetLicenseStatus_Delegate       m_fsdiGetLicenseStatus;
		private ForceSeatDI_GetTopTablePosPhy_Delegate      m_fsdiGetTopTablePosPhy;
		#endregion
	}
}
