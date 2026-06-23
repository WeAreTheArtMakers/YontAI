/**
 * Format OS name for better readability
 */
export function formatOSName(os: string, version: string): string {
  if (os === "Darwin") {
    // Extract macOS version from Darwin kernel
    const match = version.match(/Darwin Kernel Version (\d+)/);
    if (match) {
      const kernelVersion = parseInt(match[1]);
      // macOS version mapping
      if (kernelVersion >= 25) return "macOS 15 Sequoia";
      if (kernelVersion >= 24) return "macOS 14 Sonoma";
      if (kernelVersion >= 23) return "macOS 13 Ventura";
      if (kernelVersion >= 22) return "macOS 12 Monterey";
      if (kernelVersion >= 21) return "macOS 11 Big Sur";
      return `macOS (Darwin ${kernelVersion})`;
    }
    return "macOS";
  }
  
  if (os === "Windows") {
    const versionNum = version.split('.')[0];
    if (versionNum === "10") return "Windows 10";
    if (versionNum === "11") return "Windows 11";
    return `Windows ${versionNum}`;
  }
  
  if (os === "Linux") {
    // Extract distribution name if available
    const distMatch = version.match(/(\w+)\s+[\d.]+/);
    if (distMatch) {
      return `Linux (${distMatch[1]})`;
    }
    return `Linux ${version.split(' ')[0]}`;
  }
  
  // Fallback for other OS
  return `${os} ${version.split(' ')[0]}`;
}

/**
 * Format RAM display
 */
export function formatRAM(totalGB: number, usedGB: number): string {
  return `${totalGB} GB (${usedGB} GB kullanımda)`;
}
