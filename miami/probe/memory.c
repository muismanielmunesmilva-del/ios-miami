/* SPDX-License-Identifier: MIT
 * The small libc subset needed by libfdt, compiled with -fno-builtin.
 */
#include <stddef.h>
void *memcpy(void *dst, const void *src, size_t n)
{
    unsigned char *d = dst; const unsigned char *s = src;
    for (size_t i = 0; i < n; ++i) d[i] = s[i];
    return dst;
}
void *memmove(void *dst, const void *src, size_t n)
{
    unsigned char *d = dst; const unsigned char *s = src;
    if ((size_t)d < (size_t)s) return memcpy(dst, src, n);
    while (n) { --n; d[n] = s[n]; }
    return dst;
}
void *memchr(const void *src, int c, size_t n)
{
    const unsigned char *s = src;
    for (size_t i = 0; i < n; ++i) if (s[i] == (unsigned char)c) return (void *)(s+i);
    return NULL;
}
int memcmp(const void *a, const void *b, size_t n)
{
    const unsigned char *x = a, *y = b;
    for (size_t i = 0; i < n; ++i) if (x[i] != y[i]) return (int)x[i] - y[i];
    return 0;
}
size_t strlen(const char *s) { size_t n = 0; while (s[n]) ++n; return n; }
size_t strnlen(const char *s, size_t max) { size_t n = 0; while (n < max && s[n]) ++n; return n; }
char *strrchr(const char *s, int c)
{
    const char *last = NULL;
    do { if (*s == (char)c) last = s; } while (*s++);
    return (char *)last;
}
