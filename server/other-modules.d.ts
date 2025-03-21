declare module 'express-session' {
    function session(options: any): any;
    export = session;
  }
  
  declare module 'passport' {
    const passport: {
      initialize(): any;
      session(): any;
      authenticate(strategy: string, options?: any): any;
      use(strategy: any): void;
      serializeUser(callback: (user: any, done: any) => void): void;
      deserializeUser(callback: (id: any, done: any) => void): void;
    };
    export = passport;
  }
  
  declare module 'cors' {
    function cors(options?: any): any;
    export = cors;
  }