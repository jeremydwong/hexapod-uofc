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

#include "ForceSeatDI_PCH.h"

ForceSeatDI_Impl::ForceSeatDI_Impl()
	: IForceSeatDI()
	, m_handle(nullptr)
{
	m_handle = ForceSeatDI_Create();
}

ForceSeatDI_Impl::~ForceSeatDI_Impl()
{
	ForceSeatDI_Delete(m_handle);

	m_handle = nullptr;
}

bool ForceSeatDI_Impl::ConnectToUsbDevice(const wchar_t* name, const wchar_t* serialNumber)
{
	CreateHandle();

	return FSDI_True == ForceSeatDI_ConnectToUsbDevice(m_handle, name, serialNumber);
}

bool ForceSeatDI_Impl::ConnectToNetworkDevice(const char* ipAddress)
{
	CreateHandle();

	return FSDI_True == ForceSeatDI_ConnectToNetworkDevice(m_handle, ipAddress);
}

bool ForceSeatDI_Impl::TestConnection(FSDI_Bool* isConnected)
{
	return FSDI_True == ForceSeatDI_TestConnection(m_handle, isConnected);
}

bool ForceSeatDI_Impl::Park(FSDI_UINT8 parkMode)
{
	return FSDI_True == ForceSeatDI_Park(m_handle, parkMode);
}

bool ForceSeatDI_Impl::SendTopTablePosLog(const FSDI_TopTablePositionLogical* position)
{
	return FSDI_True == ForceSeatDI_SendTopTablePosLog(m_handle, position);
}

bool ForceSeatDI_Impl::SendTopTablePosPhy(const FSDI_TopTablePositionPhysical* position)
{
	return FSDI_True == ForceSeatDI_SendTopTablePosPhy(m_handle, position);
}

bool ForceSeatDI_Impl::SendTopTableMatrixPhy(const FSDI_TopTableMatrixPhysical* matrix)
{
	return FSDI_True == ForceSeatDI_SendTopTableMatrixPhy(m_handle, matrix);
}

bool ForceSeatDI_Impl::SendActuatorsPosLog(const FSDI_RequiredActuatorsPositionLogical* position)
{
	return FSDI_True == ForceSeatDI_SendActuatorsPosLog(m_handle, position);
}

bool ForceSeatDI_Impl::GetPlatformInfo(FSDI_PlatformInfo* platformInfo)
{
	return FSDI_True == ForceSeatDI_GetPlatformInfo(m_handle, platformInfo);
}

bool ForceSeatDI_Impl::GetActuatorsPosLog(FSDI_ActualActuatorsPositionLogical* position)
{
	return FSDI_True == ForceSeatDI_GetActuatorsPosLog(m_handle, position);
}

bool ForceSeatDI_Impl::GetSerialNumber(FSDI_Char sn[FSDI_SerialNumberStringLength])
{
	return FSDI_True == ForceSeatDI_GetSerialNumber(m_handle, sn);
}

bool ForceSeatDI_Impl::GetLicenseStatus(FSDI_Bool* isValid)
{
	return FSDI_True == ForceSeatDI_GetLicenseStatus(m_handle, isValid);
}

bool ForceSeatDI_Impl::GetTopTablePosPhy(FSDI_ActualTopTablePositionPhysical* position)
{
	return FSDI_True == ForceSeatDI_GetTopTablePosPhy(m_handle, position);
}

int32_t ForceSeatDI_Impl::GetRecentErrorCode()
{
	return ForceSeatDI_GetRecentErrorCode(m_handle);
}

void ForceSeatDI_Impl::CreateHandle()
{
	if (nullptr == m_handle)
	{
		m_handle = ForceSeatDI_Create();
	}
}

IMPLEMENT_MODULE(ForceSeatDI_Impl, ForceSeatDI)
