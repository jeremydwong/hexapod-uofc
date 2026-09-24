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

#pragma once

#include "IForceSeatDI.h"
#include "ForceSeatDI_Functions.h"

class ForceSeatDI_Impl : public IForceSeatDI
{
	explicit ForceSeatDI_Impl(const ForceSeatDI_Impl& other) = delete;
	explicit ForceSeatDI_Impl(const ForceSeatDI_Impl&& other) = delete;

public:
	ForceSeatDI_Impl();
	virtual ~ForceSeatDI_Impl() override;

public:
	virtual bool ConnectToUsbDevice(const wchar_t* name, const wchar_t* serialNumber) override;
	virtual bool ConnectToNetworkDevice(const char* ipAddress) override;
	virtual bool TestConnection(FSDI_Bool* isConnected) override;
	virtual bool Park(FSDI_UINT8 parkMode) override;
	virtual bool SendTopTablePosLog(const FSDI_TopTablePositionLogical* position) override;
	virtual bool SendTopTablePosPhy(const FSDI_TopTablePositionPhysical* position) override;
	virtual bool SendTopTableMatrixPhy(const FSDI_TopTableMatrixPhysical* matrix) override;
	virtual bool SendActuatorsPosLog(const FSDI_RequiredActuatorsPositionLogical* position) override;
	virtual bool GetPlatformInfo(FSDI_PlatformInfo* platformInfo) override;
	virtual bool GetActuatorsPosLog(FSDI_ActualActuatorsPositionLogical* position) override;
	virtual bool GetSerialNumber(FSDI_Char sn[FSDI_SerialNumberStringLength]) override;
	virtual bool GetLicenseStatus(FSDI_Bool* isValid) override;
	virtual bool GetTopTablePosPhy(FSDI_ActualTopTablePositionPhysical* position) override;
	virtual int32_t GetRecentErrorCode() override;

private:
	void CreateHandle();

private:
	FSDI_Handle m_handle;
};
