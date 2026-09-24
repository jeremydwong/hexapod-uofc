/*
 * Copyright (C) 2012-2026 MotionSystems
 * 
 * This file is part of ForceSeatDI SDK.
 *
 * www.motionsystems.eu
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

// #define MODE_NET_4
// #define MODE_USB_4
#define MODE_USB_ANY
using MotionSystems;
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Input;

namespace PrecisePos_CS_Win_SFX
{
	class Program
	{
		[STAThread]
		static void Main(string[] args)
		{
			List<ForceSeatDI> apis = new List<ForceSeatDI>();
			Work(ref apis);
			foreach (var api in apis)
			{
				api.Park(FSDI_ParkMode.Normal);
				api.Dispose();
			}
			apis.Clear();
		}

		static bool PrepareAPI(ref List<ForceSeatDI> apis, int index)
		{
			while (index >= apis.Count)
			{
				var api = new ForceSeatDI(@"..\..\..\.."/* path to DLL, relative to example location */);
				if (! api.IsLoaded())
				{
					api.Dispose();
					Console.WriteLine("ForceSeatDI library has not been found!");
					return false;
				}
				
				apis.Add(api);
			}

			return true;
				}

		static bool CheckPlatform(ref List<ForceSeatDI> apis, int index)
		{
				string serialNumber = "";
				if (! apis[index].GetSerialNumber(ref serialNumber))
				{
					Console.WriteLine("Failed to get platform info from {0}", index + 1);
					return false;
				}
				Console.WriteLine("Platform {0} S/N: {1}", index + 1, serialNumber);

				bool isLicenseValid = false;
				if (!apis[index].GetLicenseStatus(ref isLicenseValid))
				{
					Console.WriteLine("Failed to get license status from {0}", index + 1);
					return false;
				}

				if (!isLicenseValid)
				{
					Console.WriteLine("License is not valid for {0}", index + 1);
				}
			return true;
		}

		static bool ConnectNET(ref List<ForceSeatDI> apis, int index, string ipAddress)
		{
			if (! PrepareAPI(ref apis, index))
			{
				return false;
			}

			if (! apis[index].ConnectToNetworkDevice(ipAddress))
				{
				Console.WriteLine("Failed to connect to {0}", ipAddress);
					return false;
				}

			return CheckPlatform(ref apis, index);
			}

		static bool ConnectUSB(ref List<ForceSeatDI> apis, int index, string sn)
		{
			if (! PrepareAPI(ref apis, index))
			{
				return false;
		}

			if (! apis[index].ConnectToUsbDevice(null, sn))
			{
				Console.WriteLine("Failed to connect to {0}", sn);
				return false;
			}

			return CheckPlatform(ref apis, index);
		}

		static void Send(List<ForceSeatDI> apis, int index, ref FSDI_TopTablePositionPhysical pos, ref FSDI_SFX sfx)
		{
			if (! apis[index].SendTopTablePosPhy2(ref pos, ref sfx))
			{
				Console.WriteLine("Failed to send request to platform {0}", index + 1);
			}
		}

		static void Work(ref List<ForceSeatDI> apis)
		{
			bool ok = true;

#if (MODE_NET_4)
		// Network 4 devices
		ok = ok &&  ConnectNET(ref apis, 0, "10.1.1.75");
		ok = ok &&  ConnectNET(ref apis, 1, "10.1.1.75");
		ok = ok &&  ConnectNET(ref apis, 2, "10.1.1.75");
		ok = ok &&  ConnectNET(ref apis, 3, "10.1.1.75");
#endif
#if (MODE_USB_4)
		// USB 4 devices
		ok = ok &&  ConnectUSB(ref apis, 0, "250031-000457-315839-323120");
		ok = ok &&  ConnectUSB(ref apis, 1, "250031-000457-315839-323120");
		ok = ok &&  ConnectUSB(ref apis, 2, "250031-000457-315839-323120");
		ok = ok &&  ConnectUSB(ref apis, 3, "250031-000457-315839-323120");
#endif
#if (MODE_USB_ANY)
		// USB 1 any device
		ok = ok &&  ConnectUSB(ref apis, 0, null);
#endif

			if (!ok)
			{
				return;
			}

			Thread.Sleep(500);
			int NumberOfPlatforms = apis.Count;

			var pos = new FSDI_TopTablePositionPhysical();
			pos.structSize = (byte)Marshal.SizeOf(pos);
			pos.maxSpeed = 65535;
			pos.pause = 0;
			pos.strategy            = (byte)FSDI_Strategy.BestMatch;
			pos.accelerationProfile = (byte)FSDI_AccelerationProfile.Auto;

			var sfx = new FSDI_SFX();
			sfx.structSize = (byte)Marshal.SizeOf(sfx);

			int iterator = 0;

			Console.WriteLine("SIM started...");
			Console.WriteLine("Press 'q' to exit");

			// Configure SFX
			// Level 2 is supported by all motion platforms (including "QS"), Level 3 is supported by "QS" motion platforms.
			sfx.effect1Type = (byte)FSDI_SFX_EffectType.SinusLevel2;
			sfx.effect1Area = FSDI_SFX_AreaFlags.FrontLeft;
			sfx.effect1Amplitude = 0.05f;
			sfx.effect1Frequency = 0;
			sfx.effectsCount = 1;

			while (Keyboard.GetKeyStates(System.Windows.Input.Key.Q) == KeyStates.None)
			{
				// Prepare demo data
				float value = (float)Math.Sin(iterator * 3.1415f / 180) * 5 * 3.1415f / 180;
				sfx.effect1Frequency = (byte)(iterator / 10);
				if (++iterator > 360)
				{
					iterator = 0;
				}

				pos.roll  = value;
				pos.pitch = 0;
				Send(apis, 0, ref pos, ref sfx);

				if (NumberOfPlatforms > 1)
				{
					pos.roll  = (short)-value;
					pos.pitch = 0;
					Send(apis, 1, ref pos, ref sfx);
				}

				if (NumberOfPlatforms > 2)
				{
					pos.roll  = 0;
					pos.pitch = value;
					Send(apis, 2, ref pos, ref sfx);
				}

				if (NumberOfPlatforms > 3)
				{
					pos.roll  = 0;
					pos.pitch = (short)-value;
					Send(apis, 3, ref pos, ref sfx);
				}

				Thread.Sleep(5);
			}
			Console.WriteLine("SIM ended...");
		}
	}
}
