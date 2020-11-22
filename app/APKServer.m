//
//  APKServer.m
//  iSH
//
//  Created by Theodore Dubois on 11/21/20.
//

#import <CFNetwork/CFNetwork.h>
#import <sys/socket.h>
#import <netinet/in.h>
#import "APKServer.h"

@interface APKServer ()

@property NSFileHandle *server;

@end

@interface APKRequest : NSObject

@property NSFileHandle *client;
@property CFHTTPMessageRef message;
- (instancetype)initWithClient:(NSFileHandle *)client;

@end

static NSMutableArray<APKRequest *> *extantRequests;

@implementation APKServer

- (void)start {
    CFSocketRef socket = CFSocketCreate(kCFAllocatorDefault, AF_INET, SOCK_STREAM, 0, 0, NULL, NULL);
    if (socket == nil) {
        NSLog(@"APK server: failed to create socket");
        return;
    }
    int one = 1;
    if (setsockopt(CFSocketGetNative(socket), SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one)) != 0) {
        NSLog(@"APK server: failed to set SO_REUSEADDR");
        return;
    }
    struct sockaddr_in sin = {
        .sin_len = sizeof(sin),
        .sin_family = AF_INET,
        .sin_port = htons(42069),
        .sin_addr = INADDR_ANY,
    };
    NSData *sin_data = [NSData dataWithBytes:&sin length:sizeof(sin)];
    if (CFSocketSetAddress(socket, (CFDataRef) sin_data) != kCFSocketSuccess) {
        NSLog(@"APK server: failed to bind");
        return;
    }
    self.server = [[NSFileHandle alloc] initWithFileDescriptor:CFSocketGetNative(socket) closeOnDealloc:YES];
    [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(onAccept:) name:NSFileHandleConnectionAcceptedNotification object:self.server];
    [self.server acceptConnectionInBackgroundAndNotify];
    NSLog(@"APK server: serving");
}

- (void)onAccept:(NSNotification *)n {
    NSFileHandle *client = n.userInfo[NSFileHandleNotificationFileHandleItem];
    [extantRequests addObject:[[APKRequest alloc] initWithClient:client]];
    [self.server acceptConnectionInBackgroundAndNotify];
}

- (void)onReadable:(NSNotification *)n {

}

+ (void)initialize {
    extantRequests = [NSMutableArray new];
}

@end

@implementation APKRequest : NSObject

- (instancetype)initWithClient:(NSFileHandle *)client {
    if (self = [super init]) {
        self.client = client;
        self.message = CFHTTPMessageCreateEmpty(kCFAllocatorDefault, YES);
        [NSNotificationCenter.defaultCenter addObserver:self selector:@selector(onReadable:) name:NSFileHandleDataAvailableNotification object:client];
        [client waitForDataInBackgroundAndNotify];
    }
    return self;
}

- (void)onReadable:(NSNotification *)n {
    NSData *data = [self.client availableData];
    if (data.length == 0)
        return [self end];
    if (!CFHTTPMessageAppendBytes(self.message, data.bytes, data.length))
        return [self end];
    if (CFHTTPMessageIsHeaderComplete(self.message))
        return [self sendResponse];
    [self.client waitForDataInBackgroundAndNotify];
}

- (void)sendResponse {
    NSURL *url = CFBridgingRelease(CFHTTPMessageCopyRequestURL(self.message));
    NSArray<NSString *> *components = url.pathComponents;
    if ([components[0] isEqualToString:@"/"])
        components = [components subarrayWithRange:NSMakeRange(1, components.count - 1)];
    NSString *resourceTag = [components componentsJoinedByString:@":"];

    NSLog(@"APK server: fetching %@", resourceTag);
    NSBundleResourceRequest *request = [[NSBundleResourceRequest alloc] initWithTags:[NSSet setWithObject:resourceTag]];
    request.loadingPriority = NSBundleResourceRequestLoadingPriorityUrgent;
    [request beginAccessingResourcesWithCompletionHandler:^(NSError * _Nullable error) {
        int status = 200;
        NSData *body = nil;

        if (error != nil) {
            NSLog(@"APK server: failed to fetch %@: %@", resourceTag, error);
            status = 500;
            body = [error.description dataUsingEncoding:NSUTF8StringEncoding];
        } else {
            NSLog(@"APK server: serving %@", resourceTag);
            // TODO: this loads the entire file in memory which is wasteful and unnecessary
            body = [NSData dataWithContentsOfURL:[request.bundle URLForResource:resourceTag withExtension:nil]];
        }

        CFHTTPMessageRef response = CFHTTPMessageCreateResponse(kCFAllocatorDefault, status, NULL, kCFHTTPVersion1_1);
        CFHTTPMessageSetBody(response, CFBridgingRetain(body));
        [self.client writeData:CFBridgingRelease(CFHTTPMessageCopySerializedMessage(response))];
        CFRelease(response);
        [self end];
    }];
}

- (void)end {
    [self.client closeFile];
    self.client = nil;
    [extantRequests removeObject:self];
}

- (void)dealloc {
    [self.client closeFile];
    CFRelease(self.message);
}

@end
