import type { AxiosResponse, AxiosRequestConfig } from 'axios'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import config from '@/config'

const NETWORK_ERROR = 'Network request exception, please try again later...'

// Create an axios instance
const service = axios.create({
    baseURL: config.baseApi
})

// Request options interface
export interface RequestOptions extends Omit<AxiosRequestConfig, 'url' | 'method'> {
    headers?: Record<string, string>
    raw?: boolean // Whether to return the full response
}

// Stream request options interface
export interface StreamRequestOptions extends RequestOptions {
    signal?: AbortSignal
}

// API response type
export interface ApiResponse<T = any> {
    status: string
    data: T
    message?: string
}

// Response interceptor
service.interceptors.response.use(
    (res: AxiosResponse<ApiResponse>) => {
        const { status, data, message: msg } = res.data;
        const config = res.config as AxiosRequestConfig & RequestOptions;

        if (status === 'success') {
            // If raw is set, return the full response, otherwise return only data
            return Promise.resolve(config.raw ? res.data : data);
        } else {
            // If the backend returns an error message, display it
            ElMessage.error(msg || NETWORK_ERROR);
            return Promise.reject(res.data); // Return the full response data
        }
    },
    (error) => {
        if (error.response) {
            // If the backend returns an error response (e.g., 500), display the specific error message
            const errorMessage = error.response.data?.message || error.message;
            ElMessage.error(errorMessage || NETWORK_ERROR);
        } else {
            // For network or other errors, display a generic error message
            ElMessage.error(error.message || NETWORK_ERROR);
        }
        return Promise.reject(error);
    }
);

// HTTP request methods
class HttpClient {
    // GET request
    get<T = any, O extends RequestOptions = RequestOptions>(url: string, params: any = null, options: O = {} as O): Promise<O extends { raw: true } ? ApiResponse<T> : T> {
        return service({
            url,
            method: 'get',
            params,
            ...options
        });
    }

    // POST request
    post<T = any, O extends RequestOptions = RequestOptions>(url: string, data: any = null, options: O = {} as O): Promise<O extends { raw: true } ? ApiResponse<T> : T> {
        return service({
            url,
            method: 'post',
            data,
            ...options
        });
    }

    // PUT request
    put<T = any, O extends RequestOptions = RequestOptions>(url: string, data: any = null, options: O = {} as O): Promise<O extends { raw: true } ? ApiResponse<T> : T> {
        return service({
            url,
            method: 'put',
            data,
            ...options
        });
    }

    // DELETE request
    delete<T = any, O extends RequestOptions = RequestOptions>(url: string, params: any = null, options: O = {} as O): Promise<O extends { raw: true } ? ApiResponse<T> : T> {
        return service({
            url,
            method: 'delete',
            params,
            ...options
        });
    }

    // PATCH request
    patch<T = any, O extends RequestOptions = RequestOptions>(url: string, data: any = null, options: O = {} as O): Promise<O extends { raw: true } ? ApiResponse<T> : T> {
        return service({
            url,
            method: 'patch',
            data,
            ...options
        });
    }

    // Stream request
    stream<T = ReadableStream>(url: string, data?: any, options: StreamRequestOptions = {}): Promise<T> {
        return fetch(`${service.defaults.baseURL}${url}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
                ...options.headers
            },
            body: data ? JSON.stringify(data) : undefined,
            signal: options.signal
        }).then(response => {
            if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
            if (!response.body) throw new Error('Invalid stream response');
            return response.body as unknown as T;
        });
    }
}

const request = new HttpClient();
export default request;