declare module 'express' {
    import { EventEmitter } from 'events';
    import * as http from 'http';
    import * as https from 'https';
  
    export interface Request extends http.IncomingMessage {
      body: any;
      query: any;
      params: any;
      session?: any;
      user?: any;
    }
  
    export interface Response extends http.ServerResponse {
      json(body: any): Response;
      status(code: number): Response;
      send(body: any): Response;
    }
  
    export interface NextFunction {
      (err?: any): void;
    }
  
    export interface Application extends EventEmitter {
      use: any;
      get: any;
      post: any;
      put: any;
      delete: any;
      listen(port: number, callback?: () => void): http.Server;
    }
  
    export function json(): any;
    export function urlencoded(options: { extended: boolean }): any;
    
    function express(): Application;
    export default express;
  }