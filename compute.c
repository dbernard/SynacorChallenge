#include <stdio.h>
#include <stdlib.h>
/* compile with -02 -Wall -Wextra -o */

unsigned int cache[5][32768];
unsigned short r7;

unsigned short
checksum(unsigned short r0, unsigned short r1)
{
    if (r0 == 0)
        return (r1 + 1) % 32768;

    if (r1 == 0)
    {
        r0--;
        r1 = r7;
        if (cache[r0][r1] == 0xFFFFFFFF)
            cache[r0][r1] = checksum(r0, r1);
        return cache[r0][r1];
    }

    if (cache[r0][r1 - 1] == 0xFFFFFFFF)
        cache[r0][r1 - 1] = checksum(r0, r1 - 1);
    r1 = cache[r0][r1 - 1];

    r0--;

    if (cache[r0][r1] == 0xFFFFFFFF)
        cache[r0][r1] = checksum(r0, r1);

    return cache[r0][r1];
}

int
main()
{
    unsigned int i, j;
    for (r7 = 1; r7 != 32768; r7++)
    {
        for (i=0; i<5; i++)
        {
            for (j=0; j<32768; j++)
            {
                cache[i][j] = 0xFFFFFFFF;
            }
        }

        unsigned short res = checksum(4, 1);
        /* printf("r7: %d, checksum: %d\n", r7, res); */
        /* fflush(stdout); */

        if (r7 == 1 && res != 32765)
        {
            printf("Somethings broken\n");
            exit(1);
        }

        if (res == 6)
        {
            printf("ANSWER FOUND: r7 = %d\n", r7);
            break;
        }
    }

    return 0;
}

