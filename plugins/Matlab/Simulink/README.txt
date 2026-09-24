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

SETUP:
- Add ForceSeatDI Simulink library directory (plugins/Matlab/Simulink) to Matlab paths (HOME -> ENVIRONMENT -> Set Path)
- Open provided example project and you are ready to go

RUNNING NEW EXAMPLES:
- ForceSeatDI blocks allow to drive platforms in the "real time"
- Simulation Pacing has to be defined to use them with Matlab Simulink 
- Open Simulation Pacing Options for your project
- Enable pacing to slow down simulation
- set simulation time per wall clock second to 1

TROUBLESHOOTING:
- MotionSystems ForceSeatDI is not visible in the Library Browser
	- make sure that library folder is added to the Matlab paths
	- try to refresh Library Browser by clicking F5 keyboard button
