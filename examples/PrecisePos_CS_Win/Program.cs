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
#define PRINT_INFO

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

namespace PrecisePos_CS_Win
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

		static void Send(List<ForceSeatDI> apis, int index, ref FSDI_TopTablePositionPhysical pos)
		{
			if (! apis[index].SendTopTablePosPhy(ref pos))
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

			FSDI_ActualActuatorsPositionLogical[] actualPositions = new FSDI_ActualActuatorsPositionLogical[NumberOfPlatforms];
			FSDI_PlatformInfo[]                   platformInfos   = new FSDI_PlatformInfo[NumberOfPlatforms];
			FSDI_ActualTopTablePositionPhysical[] topTablePos     = new FSDI_ActualTopTablePositionPhysical[NumberOfPlatforms];
			for (int i = 0; i < NumberOfPlatforms; ++i)
			{
				actualPositions[i] = new FSDI_ActualActuatorsPositionLogical();
				actualPositions[i].structSize = (byte)Marshal.SizeOf(actualPositions[i]);

				platformInfos[i] = new FSDI_PlatformInfo();
				platformInfos[i].structSize = (byte)Marshal.SizeOf(platformInfos[i]);

				topTablePos[i] = new FSDI_ActualTopTablePositionPhysical();
				topTablePos[i].structSize = (byte)Marshal.SizeOf(topTablePos[i]);
			}

			int iterator = 0;

			QueryPerfCounter counter = new QueryPerfCounter();

			Console.WriteLine("SIM started...");
			Console.WriteLine("Press 'q' to exit");
			while (Keyboard.GetKeyStates(System.Windows.Input.Key.Q) == KeyStates.None)
			{
				// Prepare demo data
				float value = (float)Math.Sin(iterator * 3.1415f / 180) * 5 * 3.1415f / 180;
				if (++iterator > 360)
				{
					iterator = 0;
				}

				// Send new requests
				counter.Start();

				pos.roll  = value;
				pos.pitch = 0;
				Send(apis, 0, ref pos);

				if (NumberOfPlatforms > 1)
				{
					pos.roll  = (short)-value;
					pos.pitch = 0;
					Send(apis, 1, ref pos);
				}

				if (NumberOfPlatforms > 2)
				{
					pos.roll  = 0;
					pos.pitch = value;
					Send(apis, 2, ref pos);
				}

				if (NumberOfPlatforms > 3)
				{
					pos.roll  = 0;
					pos.pitch = (short)-value;
					Send(apis, 3, ref pos);
				}

				// Read current actuators position
				for (int i = 0; i < NumberOfPlatforms; ++i)
				{
					if (! apis[i].GetActuatorsPosLog(ref actualPositions[i]))
					{
						Console.WriteLine("Failed to get actuator pos from {0}", i + 1);
					}
					if (! apis[i].GetPlatformInfo(ref platformInfos[i]))
					{
						Console.WriteLine("Failed to get platform info from {0}", i + 1);
					}
					if (!apis[i].GetTopTablePosPhy(ref topTablePos[i]))
					{
						Console.WriteLine("Failed to get top table pos from {0}", i + 1);
					}
				}

				counter.Stop();
				Console.WriteLine("It took {0} (ms)", counter.Duration());

#if (PRINT_INFO)
				for (int i = 0; i < NumberOfPlatforms; ++i)
				{
					Console.Write("Platform: {0} ", i + 1);
					Console.WriteLine("Pos: {0}, {1}, {2}, {3}, {4}, {5}",
						actualPositions[i].actualMotorPosition1,
						actualPositions[i].actualMotorPosition2,
						actualPositions[i].actualMotorPosition3,
						actualPositions[i].actualMotorPosition4,
						actualPositions[i].actualMotorPosition5,
						actualPositions[i].actualMotorPosition6);
					Console.WriteLine("    Error code: {0}.{1}",
						(int)platformInfos[i].moduleErrorCode,
						(int)platformInfos[i].moduleErrorIndex);
					Console.WriteLine("    Top Frame: roll {0}, pitch {1}, yaw {2}, heave {3}, surge {4}, sway {5}",
						topTablePos[i].roll,
						topTablePos[i].pitch,
						topTablePos[i].yaw,
						topTablePos[i].heave,
						topTablePos[i].surge,
						topTablePos[i].sway);
				}
#endif
				Thread.Sleep(5);
			}
			Console.WriteLine("SIM ended...");
		}
	}

	public class QueryPerfCounter
	{
		[DllImport("KERNEL32")]
		private static extern bool QueryPerformanceCounter(out long lpPerformanceCount);

		[DllImport("Kernel32.dll")]
		private static extern bool QueryPerformanceFrequency(out long lpFrequency);

		private long start;
		private long stop;
		private long frequency;

		public QueryPerfCounter()
		{
			if (QueryPerformanceFrequency(out frequency) == false)
			{
				// Frequency not supported
				throw new Win32Exception();
			}
		}

		public void Start()
		{
			QueryPerformanceCounter(out start);
		}

		public void Stop()
		{
			QueryPerformanceCounter(out stop);
		}

		public double Duration()
		{
			return ((double)(stop - start) * 1000.0) / (double)frequency;
		}
	}
}
