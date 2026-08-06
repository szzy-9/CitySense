/**
 * Keeps raw exception text out of the interface.
 *
 * A failed `fetch` throws "Failed to fetch", and that string used to be shown
 * to the user verbatim. This app is read by people who are already anxious, so
 * every message on screen has to be written for them, not for the console.
 *
 * Throw `new UserFacingError(message)` when the wording is meant to be read by
 * a person, and pass anything else through `messageForError` to get a calm
 * fallback instead of the browser's own words.
 */

/** An error whose message was written for a person to read. */
export class UserFacingError extends Error {
  constructor(message) {
    super(message);
    this.name = "UserFacingError";
  }
}

export function messageForError(error, fallbackMessage) {
  return error instanceof UserFacingError ? error.message : fallbackMessage;
}
