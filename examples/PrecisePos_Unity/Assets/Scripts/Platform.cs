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

using MotionSystems;
using System.Runtime.InteropServices;
using UnityEngine;

public class Platform : MonoBehaviour
{
    // Platform physical min/max coordinates
    private const int PLATFORM_POSITION_PHY_ANGLE_DEG_MIN = -8;
    private const int PLATFORM_POSITION_PHY_ANGLE_DEG_MAX = 8;
    private const int PLATFORM_POSITION_PHY_TRAVEL_MM_MIN = -100;
    private const int PLATFORM_POSITION_PHY_TRAVEL_MM_MAX = 100;

    // Heave maximum value that is available in the game
    private const float DRAWING_HEAVE_MAX = 1.0f;

    // Heave change step
    private const float DRAWING_HEAVE_STEP = 0.05f;

    // Maximum value of pitch angle that is available in the game
    private const float DRAWING_PITCH_MAX = 16;

    // Pitch change step
    private const float DRAWING_PITCH_STEP = 1;

    // Maximum value of roll angle that is available in the game
    private const float DRAWING_ROLL_MAX = 16;

    // Pitch change step
    private const float DRAWING_ROLL_STEP = 1;

    // Shaft object
    private GameObject m_shaft = null;

    // Board object
    private GameObject m_board = null;

    // Origin position of the shaft
    private Vector3 m_originPosition;

    // Origin rotation of the board
    private Vector3 m_originRotation;

    // Current platform's heave in game
    private float m_heave = 0;

    // Current platform's pitch in game
    private float m_pitch = 0;

    // Current platform's roll in game
    private float m_roll = 0;

    // FSDI api
    private ForceSeatDI m_fsdi;
    private bool m_isConnected = false;
    private bool m_isLicenseValid = false;

    // Position in logical coordinates that will be send to the platform
    private FSDI_TopTablePositionPhysical m_platformPosition      = new FSDI_TopTablePositionPhysical();
    private FSDI_ActualActuatorsPositionLogical m_actualPositions = new FSDI_ActualActuatorsPositionLogical();
    private FSDI_PlatformInfo m_platformInfos                     = new FSDI_PlatformInfo();
    private FSDI_ActualTopTablePositionPhysical m_topTablePos     = new FSDI_ActualTopTablePositionPhysical();

    void Start ()
    {
        // Load ForceSeatDI library
        // ForceSeatDI - BEGIN
        m_fsdi = new ForceSeatDI("Assets/ForceSeatDI");

        if (m_fsdi.IsLoaded())
        {
            m_isConnected = m_fsdi.ConnectToUsbDevice(null, null);

            if (!m_isConnected)
            {
                Debug.LogError("Failed to connect to USB device!");
                return;
            }

            m_fsdi.GetLicenseStatus(ref m_isLicenseValid);
            if (!m_isLicenseValid)
            {
                Debug.LogError("License is not valid!");
                return;
            }

            // Find platform's components
            m_shaft = GameObject.Find("Shaft");
            m_board = GameObject.Find("Board");

            SaveOriginPosition();
            SaveOriginRotation();

            // Prepare data structure by clearing it and setting correct size
            m_platformPosition.structSize = (byte)Marshal.SizeOf(m_platformPosition);
            m_platformPosition.maxSpeed   = 65535;
            m_platformPosition.pause      = 0;
            m_platformPosition.strategy   = (byte)FSDI_Strategy.BestMatch;

            m_actualPositions.structSize = (byte)Marshal.SizeOf(m_actualPositions);
            m_platformInfos.structSize   = (byte)Marshal.SizeOf(m_platformInfos);
            m_topTablePos.structSize     = (byte)Marshal.SizeOf(m_topTablePos);

            SendDataToPlatform();
            // ForceSeatDI - END
        }
        else
        {
            Debug.LogError("ForceSeatDI library has not been found!");
        }
    }

    void Update ()
    {
        // ForceSeatDI - BEGIN
        if (m_fsdi.IsLoaded() && m_isConnected && m_isLicenseValid)
        {
            // Set back origin position and then modify it
            m_shaft.transform.position = m_originPosition;
            m_shaft.transform.Translate(0, m_heave, 0);

            // Set back origin rotation and then modify it
            m_board.transform.eulerAngles = m_originRotation;
            m_board.transform.Rotate(m_pitch, 0, -m_roll);

            SendDataToPlatform();

            m_fsdi.GetActuatorsPosLog(ref m_actualPositions);
            m_fsdi.GetPlatformInfo(ref m_platformInfos);
            m_fsdi.GetTopTablePosPhy(ref m_topTablePos);
        }
        // ForceSeatDI - END
    }

    void FixedUpdate()
    {
        // Update values in order to received user's input
        UpdateValue(ref m_pitch, Input.GetAxis("Vertical"),           DRAWING_PITCH_STEP, -DRAWING_PITCH_MAX, DRAWING_PITCH_MAX);
        UpdateValue(ref m_roll,  Input.GetAxis("Horizontal"),         DRAWING_ROLL_STEP,   -DRAWING_ROLL_MAX, DRAWING_ROLL_MAX);
        UpdateValue(ref m_heave, Input.GetKey(KeyCode.Space) ? 1 : 0, DRAWING_HEAVE_STEP,                  0, DRAWING_HEAVE_MAX);
    }
    
    void OnDestroy()
    {
        // ForceSeatDI - BEGIN
        if (m_fsdi.IsLoaded())
        {
            m_fsdi.Park(FSDI_ParkMode.Normal);
            m_fsdi.Dispose();
        }
        // ForceSeatDI - END
    }

    private void UpdateValue(ref float value, float input, float step, float min, float max)
    {
        if (0 < input)
        {
            value = Mathf.Clamp(value + step, min, max);
        }
        else if (0 > input)
        {
            value = Mathf.Clamp(value - step, min, max);
        }
        else if (value > 0)
        {
            value = Mathf.Clamp(value - step, 0, max);
        }
        else if (value < 0)
        {
            value = Mathf.Clamp(value + step, min, 0);
        }
    }

    private void SaveOriginPosition()
    {
        // Save origin position of the platform's shaft
        var x = m_shaft.transform.position.x;
        var y = m_shaft.transform.position.y;
        var z = m_shaft.transform.position.z;

        m_originPosition = new Vector3(x, y, z);
    }

    private void SaveOriginRotation()
    {
        // Save origin rotation of the platform's board
        var x = m_board.transform.eulerAngles.x;
        var y = m_board.transform.eulerAngles.y;
        var z = m_board.transform.eulerAngles.z;

        m_originRotation = new Vector3(x, y, z);
    }

    private void SendDataToPlatform()
    {
        // Convert parameters to logical units
        m_platformPosition.pause = 0;
        m_platformPosition.roll  = Mathf.Clamp(m_roll  / DRAWING_ROLL_MAX  * PLATFORM_POSITION_PHY_ANGLE_DEG_MAX * Mathf.Deg2Rad, PLATFORM_POSITION_PHY_ANGLE_DEG_MIN * Mathf.Deg2Rad, PLATFORM_POSITION_PHY_ANGLE_DEG_MAX * Mathf.Deg2Rad);
        m_platformPosition.pitch = Mathf.Clamp(m_pitch / DRAWING_PITCH_MAX * PLATFORM_POSITION_PHY_ANGLE_DEG_MAX * Mathf.Deg2Rad, PLATFORM_POSITION_PHY_ANGLE_DEG_MIN * Mathf.Deg2Rad, PLATFORM_POSITION_PHY_ANGLE_DEG_MAX * Mathf.Deg2Rad);
        m_platformPosition.heave = Mathf.Clamp(m_heave / DRAWING_HEAVE_MAX * PLATFORM_POSITION_PHY_TRAVEL_MM_MAX, PLATFORM_POSITION_PHY_TRAVEL_MM_MIN, PLATFORM_POSITION_PHY_TRAVEL_MM_MAX);

        // Send data to platform
        m_fsdi.SendTopTablePosPhy(ref m_platformPosition);
    }
}
