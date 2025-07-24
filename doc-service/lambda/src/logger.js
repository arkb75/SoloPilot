/**
 * Simple CloudWatch-compatible logger
 */
class Logger {
  constructor() {
    this.context = {};
  }

  setContext(additionalContext) {
    this.context = { ...this.context, ...additionalContext };
  }

  log(level, message, data = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      ...this.context,
      ...data
    };

    // CloudWatch will automatically parse JSON logs
    console.log(JSON.stringify(logEntry));
  }

  info(message, data) {
    this.log('INFO', message, data);
  }

  warn(message, data) {
    this.log('WARN', message, data);
  }

  error(message, data) {
    this.log('ERROR', message, data);
  }

  debug(message, data) {
    if (process.env.LOG_LEVEL === 'DEBUG') {
      this.log('DEBUG', message, data);
    }
  }
}

// Export singleton logger
let logger;

exports.createLogger = () => {
  if (!logger) {
    logger = new Logger();
  }
  return logger;
};
