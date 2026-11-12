export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 256;

export interface SetupValues {
  password: string;
  confirm: string;
  deviceName: string;
  setupCode: string;
}

export interface SetupErrors {
  password?: string;
  confirm?: string;
  deviceName?: string;
  setupCode?: string;
}

export function passwordProblem(password: string): string | undefined {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (password.length > MAX_PASSWORD_LENGTH) {
    return `Use ${MAX_PASSWORD_LENGTH} characters or fewer.`;
  }
  return undefined;
}

export function confirmProblem(password: string, confirm: string): string | undefined {
  return confirm === password ? undefined : "The passwords do not match.";
}

export function deviceNameProblem(deviceName: string): string | undefined {
  return deviceName.trim() === "" ? "Enter a name for this browser." : undefined;
}

export function setupCodeProblem(setupCode: string): string | undefined {
  return setupCode.trim() === "" ? "Enter the setup code from the server configuration." : undefined;
}

export function validateSetup({ password, confirm, deviceName, setupCode }: SetupValues): SetupErrors {
  return {
    password: passwordProblem(password),
    confirm: confirmProblem(password, confirm),
    deviceName: deviceNameProblem(deviceName),
    setupCode: setupCodeProblem(setupCode),
  };
}

export function hasSetupErrors(errors: SetupErrors): boolean {
  return Object.values(errors).some((problem) => problem !== undefined);
}
