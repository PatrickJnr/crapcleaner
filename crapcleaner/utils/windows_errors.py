import re

WINDOWS_ERROR_MAP: dict[str, tuple[str, str]] = {
    "0x80244007": (
        "SOAP Client Fault",
        "Communication with the Microsoft Update server failed (SOAP fault). Check your internet connection or proxy settings.",
    ),
    "0x80244008": (
        "Update Server Communication Failure",
        "The update client could not communicate with the update server. Ensure active internet connectivity.",
    ),
    "0x8024400E": (
        "Server XML Parsing Error",
        "The update server returned an invalid response or XML data could not be parsed.",
    ),
    "0x80244011": (
        "Update Server Connection Failure",
        "Could not connect to the Windows Update server (SOAP fault). Check your internet connection, proxy settings, or VPN.",
    ),
    "0x80244016": (
        "HTTP 400 Bad Request",
        "The update request format was rejected by the server.",
    ),
    "0x80244017": (
        "HTTP 401 Unauthorized",
        "Access to the update server requires authentication credentials.",
    ),
    "0x80244018": (
        "HTTP 403 Forbidden",
        "Access to the update server was denied (HTTP 403 Forbidden). A network proxy or firewall may be blocking Windows Update.",
    ),
    "0x80244019": (
        "HTTP 404 Not Found",
        "The requested update catalog or package was not found on the update server.",
    ),
    "0x8024401A": (
        "HTTP 405 Method Not Allowed",
        "The update server does not support the requested HTTP method.",
    ),
    "0x8024401B": (
        "HTTP 407 Proxy Authentication Required",
        "Your network proxy requires authentication before Windows Update can reach the internet.",
    ),
    "0x8024401C": (
        "HTTP 408 Request Timeout",
        "The update server connection timed out while waiting for a response.",
    ),
    "0x8024401D": (
        "HTTP 409 Conflict",
        "A conflict occurred with the update resource on the server.",
    ),
    "0x8024401E": (
        "HTTP 410 Gone",
        "The requested update resource is no longer available on the server.",
    ),
    "0x8024401F": (
        "HTTP 500 Server Error",
        "Microsoft Update servers encountered an internal error. Please try again later or use Windows Settings.",
    ),
    "0x80244020": (
        "HTTP 501 Not Implemented",
        "The update server does not support the required functionality.",
    ),
    "0x80244021": (
        "HTTP 502 Bad Gateway",
        "The network proxy or gateway received an invalid response from Microsoft Update servers.",
    ),
    "0x80244022": (
        "HTTP 503 Service Unavailable",
        "Windows Update servers are temporarily overloaded or undergoing maintenance. Try again later.",
    ),
    "0x80244023": (
        "HTTP 504 Gateway Timeout",
        "The network gateway timed out waiting for the update server response.",
    ),
    "0x8024402C": (
        "DNS Name Resolution Failure",
        "Windows Update could not resolve the server address via DNS. Check your network DNS configuration.",
    ),
    "0x8024002E": (
        "Windows Update Disabled by Policy",
        "Access to Windows Update is blocked by Group Policy, MDM, or registry configuration.",
    ),
    "0x80240025": (
        "Action Not Permitted",
        "Group Policy prevents standard users from performing this update action. Administrator privileges may be required.",
    ),
    "0x8024500C": (
        "Redirector Blocked by Policy",
        "Connections to the update redirector server are disallowed by system policy.",
    ),
    "0x80240017": (
        "Operation Not Supported",
        "The requested update operation is not supported on this Windows edition.",
    ),
    "0x80240016": (
        "Operation Already in Progress",
        "Another update search, download, or installation is already running in the background.",
    ),
    "0x8024001E": (
        "Update Service Stopping",
        "The operation could not complete because the Windows Update service (wuauserv) was stopping.",
    ),
    "0x80240020": (
        "Update Handler Initialization Failed",
        "The automatic update handler failed to initialize.",
    ),
    "0x80240024": (
        "No Updates Found",
        "No updates matched the search query criteria.",
    ),
    "0x8024A000": (
        "Automatic Updates Unavailable",
        "The Automatic Updates service was unable to service incoming requests.",
    ),
    "0x80248007": (
        "Datastore Error",
        "The local Windows Update cache database (SoftwareDistribution) is missing or corrupted.",
    ),
    "0x80248014": (
        "Datastore Uninitialized",
        "The local update database could not be initialized or opened.",
    ),
    "0x8024800C": (
        "Datastore Schema Mismatch",
        "The update datastore schema is incompatible or corrupted.",
    ),
    "0x80240034": (
        "Update Download Failed",
        "Failed to download one or more update packages. Check disk space and network connection.",
    ),
    "0x80246002": (
        "Package Hash Mismatch",
        "Downloaded update file failed hash verification (corrupted download). Retrying usually resolves this.",
    ),
    "0x80246008": (
        "BITS Service Connection Failed",
        "Failed to connect to Background Intelligent Transfer Service (BITS). Ensure the BITS service is running.",
    ),
    "0x80242006": (
        "Corrupted Update Metadata",
        "Update metadata could not be parsed or is corrupted.",
    ),
    "0x8024200B": (
        "Update Installation Failed",
        "The update installer returned a failure code during installation.",
    ),
    "0x80240438": (
        "Security Verification Failed",
        "Connection failed due to proxy/firewall SSL inspection or missing TLS cipher suites.",
    ),
    "0x80072EE2": (
        "Internet Connection Timeout",
        "The connection to Microsoft Update servers timed out. Check your internet connection or firewall.",
    ),
    "0x80072EFD": (
        "Cannot Connect to Server",
        "Failed to establish a connection to Windows Update servers. Ensure an active internet connection.",
    ),
    "0x80072EE7": (
        "Server Name Resolution Failed",
        "Could not resolve the update server address. Check your DNS and network adapter settings.",
    ),
    "0x80072F8F": (
        "Certificate / System Clock Error",
        "A security certificate error occurred. Verify that your computer's date and time are set accurately.",
    ),
    "0x80072EFE": (
        "Connection Aborted",
        "The connection with the update server was terminated abnormally.",
    ),
    "0x80070422": (
        "Service is Disabled",
        "The Windows Update service (wuauserv) or a required dependency service is disabled in Windows Services.",
    ),
    "0x80070424": (
        "Service Does Not Exist",
        "The specified Windows service is not installed or its registry entry is missing.",
    ),
    "0x80070426": (
        "Service Not Started",
        "The service has not been started. Start the service before retrying.",
    ),
    "0x8007041D": (
        "Service Response Timeout",
        "The service did not respond to the start or control request in a timely fashion.",
    ),
    "0x80070437": (
        "Service Account Invalid",
        "The account specified for this service differs from the account specified for other services.",
    ),
    "0x80070005": (
        "Access Denied",
        "Administrator privileges are required to perform this action. Run the application as Administrator.",
    ),
    "0x80070002": (
        "File Not Found",
        "A required system file was not found during the update operation.",
    ),
    "0x80070003": (
        "Path Not Found",
        "A required system path could not be found.",
    ),
    "0x8007007E": (
        "Module Not Found",
        "A required system module or DLL could not be located.",
    ),
    "0x80070490": (
        "Component Store Corruption",
        "Element not found \u2014 Windows servicing component store (CBS) may need repair with DISM / SFC.",
    ),
    "0x80070643": (
        "Installation Error",
        "Fatal error during update installation (often caused by .NET Framework or Windows Installer cache).",
    ),
    "0x80080005": (
        "COM Server Execution Failed",
        "Failed to start or connect to the Windows Update Session COM server.",
    ),
    "0x80040154": (
        "COM Class Not Registered",
        "The Windows Update COM component is not registered on this system.",
    ),
}

_HEX_CODE_RE = re.compile(r"0x[0-9a-fA-F]{8}")


def extract_error_code(text: str) -> str | None:
    if not text:
        return None
    match = _HEX_CODE_RE.search(text)
    return match.group(0).lower() if match else None


def explain_windows_error(raw_error: str | None) -> str:
    if not raw_error:
        return ""

    raw_clean = str(raw_error).strip()
    code = extract_error_code(raw_clean)
    
    if code:
        code_norm = f"0x{code[2:].lower()}"
        code_display = f"0x{code[2:].upper()}"
        
        for key, (summary, detail) in WINDOWS_ERROR_MAP.items():
            if key.lower() == code_norm:
                return f"{summary} ({code_display}): {detail}"

        if code_norm.startswith("0x80244"):
            return f"Update Server Error ({code_display}): Windows Update encountered a communication or server error. Check your internet connection or proxy settings."
        if code_norm.startswith("0x80248"):
            return f"Update Datastore Error ({code_display}): Windows Update local cache database error. Clearing SoftwareDistribution may resolve this."
        if code_norm.startswith("0x80246") or code_norm.startswith("0x8024003"):
            return f"Update Download Error ({code_display}): Windows Update failed to download update packages."
        if code_norm.startswith("0x80072"):
            return f"Network Timeout / Connection Error ({code_display}): Failed to establish a connection to Windows Update servers."
        if code_norm.startswith("0x800704"):
            return f"Service Configuration Error ({code_display}): Windows Update service or a dependent service is disabled or failed to start."
        if code_norm.startswith("0x80070005"):
            return f"Access Denied ({code_display}): Administrator privileges are required to perform this operation."
        if code_norm.startswith("0x80070"):
            return f"System Error ({code_display}): Windows system service or file error during update operation."
        
        return f"Windows Error ({code_display}): An error occurred during the update operation ({raw_clean})."

    low = raw_clean.lower()
    
    if "access is denied" in low or "unauthorized" in low:
        return "Access Denied: Administrator privileges are required to perform this operation."
    if "wuauserv is not running" in low or "service is stopped" in low:
        return "Service Stopped: The Windows Update service (wuauserv) is not running. Enable and start it in Windows Services."
    if "timed out" in low:
        return "Connection Timeout: The operation timed out waiting for a response from Windows Update servers."
    if "cannot find the file" in low or "not found" in low:
        return f"Resource Not Found: {raw_clean}"

    return raw_clean