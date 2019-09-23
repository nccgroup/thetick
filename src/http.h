/*
 * The Tick, a Linux embedded backdoor.
 * 
 * Released as open source by NCC Group Plc - http://www.nccgroup.com/
 * Developed by Mario Vilas, mario.vilas@nccgroup.com
 * http://www.github.com/nccgroup/thetick
 * 
 * See the LICENSE file for further details.
*/

#ifndef HTTP_H
#define HTTP_H

void http_init();
void http_cleanup();
int download_file(const char *url, const char *filename, long verify_peer);

#endif /* HTTP_H */
