
#include "geomag.h"
#include <time.h>
#include <math.h>


static char usage[] = " Usage:\n"
                      "   magdec lon lat [year [month [day]]]\n"
                      "     lon, lat: in decimal degrees\n"
                      "     year, month, day: integer date\n"
                      "          or just decimal year\n"
                      "   If no date is given, the present date is used\n"
                      "   1 is substituted for missing month and/or day\n\n"
                      "   Prints to stdout: 4 floating point"
                      "  numbers separated by spaces:\n"
                      "     declination, inclination in degrees\n"
                      "     horizontal field, total field in nanoTeslas\n\n"
                      " "
                      " Note: this version uses IGRF11, released in Dec. 2009."
                      "       Model parameters are hard-coded; no external"
                      "       file is needed."
                      "";


int main(int argc, char **argv)
{
    struct model_t **model_array;
    int nmodels;
    double dtest, itest, htest, ftest;
    int year, month, day;
    double dyear;
    double lon, lat;
    struct tm *now;
    time_t now_seconds;
    int nscan;

    if (argc < 3 || argc > 6)
    {
        puts(usage);
        return 1;
    }

    nscan = sscanf(argv[1], "%lf", &lon);
    nscan += sscanf(argv[2], "%lf", &lat);

    if (nscan != 2)
    {
        puts(usage);
        return 1;
    }


    if (argc == 3)
    {
        now_seconds = time(NULL);
        now = gmtime(&now_seconds);
        year = now->tm_year + 1900;
        month = now->tm_mon + 1;
        day = now->tm_mday;
    }
    else
    {
        if (argc == 4)
        {
            dyear = atof(argv[3]);
            /* the rest won't actually be used in this case */
            year = (int)dyear;
            month = 1 + (int)((dyear - year) * 12);
            day = 1;
        }
        if (argc > 4)
        {
            year = atoi(argv[3]);
            month = atoi(argv[4]);
            day = 1;
        }
        if (argc == 6)
        {
            day = atoi(argv[5]);
        }
    }

    if (argc != 4)
    {
        dyear = julday(month, day, year);
        /* julday function is mis-named--it simply returns decimal year */
    }

    while (lon > 180.0)
    {
        lon -= 360.0;
    }
    while (lon < -180.0)
    {
        lon += 360.0;
    }
    /* printf("lon %lf lat %lf dyear %lf year %d month %d day %d\n",
     *       lon, lat, dyear, year, month, day);
     */

    nmodels = models_from_lines(&model_array);

    dihf_from_models(model_array, nmodels,
                        dyear, lon, lat,
                        &dtest, &itest, &htest, &ftest);
    printf("%lf %lf %lf %lf\n",
              dtest, itest, htest, ftest);

    free_models(model_array, nmodels);
    return 0;
}

