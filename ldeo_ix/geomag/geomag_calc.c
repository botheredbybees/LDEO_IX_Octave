/*
    The core calculation subroutines are here.
    The first set were added be Eric Firing to modernize
    the reading and handling of the model data, but are
    otherwise based on code from the original geomag61.c.
    The second set of subroutines are identical to the originals,
    or are lightly modified to use the new model data structure
    and to avoid the use of global variables.

*/

#include "geomag.h"
#include "igrf11.h"  /* initializes model_lines */

#define LINEBUFSIZE 90 /* leave some slop */

int models_from_lines(struct model_t ***model_array)
/* May want to change this to return the array of pointers and use
   a pointer to an int to return the length or error code; as it
   is, triple dereferencing is getting confusing.
*/

{
    struct model_t model;
    struct model_t *mod_ptr, *prev_mod_ptr, *first_mod_ptr;
    struct model_t **models;
    char buf[LINEBUFSIZE];
    char *c;
    int nmodels = 0;
    int ret; /* used for error return cases of "goto error;" */
    int nscan;
    int ii;
    int iline=0;


    while (1)
    {
        strcpy(buf, model_lines[iline]);
        iline++;
        if (strlen(buf) != RECLEN) break;

        if (!strncmp(buf,"   ", 3))
        {
            if (nmodels)
            {
                prev_mod_ptr = mod_ptr;
            }
            mod_ptr = malloc(sizeof(struct model_t));
            if (mod_ptr == NULL)
            {
                ret = -2;
                goto error;
            }
            mod_ptr->next = NULL;
            if (nmodels)
            {
                prev_mod_ptr->next = mod_ptr;
            }
            else
            {
                first_mod_ptr = mod_ptr;
            }
            nmodels++;  /* Now it can be used for deallocation on error */
            nscan = sscanf(buf, "%s%lf%d%d%d%lf%lf%lf%lf",
                                  mod_ptr->name, &mod_ptr->epoch,
                                  &mod_ptr->max1, &mod_ptr->max2,
                                  &mod_ptr->max3, &mod_ptr->yrmin,
                                  &mod_ptr->yrmax, &mod_ptr->altmin,
                                  &mod_ptr->altmax);
            if (nscan != 9)
            {
                ret = -3;
                goto error;
            }
            ii = 0;  /* initialized for reading coefficients */
        }
        else
        {
            int mm, nn;

            if (nmodels < 1)
            {
                ret = -4;
                goto error;
            }

           for ( nn = 1; nn <= mod_ptr->max1; ++nn)
           {
              for (mm = 0; mm <= nn; ++mm)
              {
                 int m, n;
                 double f1, f2, f3, f4;
                 int nscan2, nscan3;

                 /* Read a new line only if we have already used the line. */
                 if (buf[0] == '\0')
                 {
                    strcpy(buf, model_lines[iline]);
                    iline++;
                 }

                 nscan = sscanf(buf, "%d %d %lf %lf %lf %lf", /*  %8s%d", */
                                  &n, &m, &f1, &f2, &f3, &f4);
                                                    /*, irat, &line_num); */

                 if (nscan != 6)
                 {
                    ret = -5;
                    // printf("nscan=%d\n", nscan);
                    // printf("%s\n", buf);
                    goto error;
                 }
                 if ((nn != n) || (mm != m))
                 {
                    ret = -6;
                    // printf("nn, n, mm, m: %d %d  %d %d\n", nn, n, mm, m);
                    // printf("%s\n", buf);
                    goto error;
                 }
                 ii++; /* 1-based arrays */
                 mod_ptr->gh[ii] = f1;
                 mod_ptr->ghr[ii] = f3;
                 if (m != 0)
                 {
                    ii++;
                    mod_ptr->gh[ii] = f2;
                    mod_ptr->ghr[ii] = f4;
                 }
                 buf[0] = '\0';  /* flag: read a new line */
              }
           }
        }
    }
    models = (struct model_t **)malloc(nmodels * sizeof(void *));
    if (models == NULL)
    {
        return(-6);
    }
    mod_ptr = first_mod_ptr;
    for (ii=0; ii<nmodels; ii++)
    {
        models[ii] = mod_ptr;
        mod_ptr = mod_ptr->next;
    }
    *model_array = models;
    return nmodels;

    error:
    /* Clean up by working forward through the linked list. */
    for (ii=0; ii<nmodels; ii++)
    {
        mod_ptr = first_mod_ptr->next;
        if (first_mod_ptr) free(first_mod_ptr);
        first_mod_ptr = mod_ptr;
    }
    return ret;
}



int models_from_file(char *filename, struct model_t ***model_array)
/* May want to change this to return the array of pointers and use
   a pointer to an int to return the length or error code; as it
   is, triple dereferencing is getting confusing.
*/

{
    struct model_t model;
    struct model_t *mod_ptr, *prev_mod_ptr, *first_mod_ptr;
    struct model_t **models;
    FILE *modfile;
    char buf[LINEBUFSIZE];
    char *c;
    int nmodels = 0;
    int ret; /* used for error return cases of "goto error;" */
    int nscan;
    int ii;


    modfile = fopen(filename, "rb"); /* handle line endings ourselves */
    if (modfile == NULL) return(-1);
    while (!feof(modfile))
    {
        fgets(buf, LINEBUFSIZE, modfile);
        for (c = buf; *c; c++)
        {
            if (*c == '\n' || *c == '\r')
            {
                *c = '\0';
                break;
            }
        }

        if (strlen(buf) != RECLEN) continue;

        if (!strncmp(buf,"   ", 3))
        {
            if (nmodels)
            {
                prev_mod_ptr = mod_ptr;
            }
            mod_ptr = malloc(sizeof(struct model_t));
            if (mod_ptr == NULL)
            {
                ret = -2;
                goto error;
            }
            mod_ptr->next = NULL;
            if (nmodels)
            {
                prev_mod_ptr->next = mod_ptr;
            }
            else
            {
                first_mod_ptr = mod_ptr;
            }
            nmodels++;  /* Now it can be used for deallocation on error */
            nscan = sscanf(buf, "%s%lf%d%d%d%lf%lf%lf%lf",
                                  mod_ptr->name, &mod_ptr->epoch,
                                  &mod_ptr->max1, &mod_ptr->max2,
                                  &mod_ptr->max3, &mod_ptr->yrmin,
                                  &mod_ptr->yrmax, &mod_ptr->altmin,
                                  &mod_ptr->altmax);
            if (nscan != 9)
            {
                ret = -3;
                goto error;
            }
            ii = 0;  /* initialized for reading coefficients */
        }
        else
        {
            int mm, nn;

            if (nmodels < 1)
            {
                ret = -4;
                goto error;
            }

           for ( nn = 1; nn <= mod_ptr->max1; ++nn)
           {
              for (mm = 0; mm <= nn; ++mm)
              {
                 int m, n;
                 double f1, f2, f3, f4;
                 int nscan2, nscan3;

                 /* Read a new line only if we have already used the line. */
                 if (buf[0] == '\0')
                 {
                     /* Read a line and chop off the line ending. */
                     fgets(buf, LINEBUFSIZE, modfile);
                     for (c = buf; *c; c++)
                     {
                         if (*c == '\n' || *c == '\r')
                         {
                             *c = '\0';
                             break;
                         }
                     }
                 }

                 nscan = sscanf(buf, "%d %d %lf %lf %lf %lf", /*  %8s%d", */
                                  &n, &m, &f1, &f2, &f3, &f4);
                                                    /*, irat, &line_num); */

                 if (nscan != 6)
                 {
                    ret = -5;
                    // printf("nscan=%d\n", nscan);
                    // printf("%s\n", buf);
                    goto error;
                 }
                 if ((nn != n) || (mm != m))
                 {
                    ret = -6;
                    // printf("nn, n, mm, m: %d %d  %d %d\n", nn, n, mm, m);
                    // printf("%s\n", buf);
                    goto error;
                 }
                 ii++; /* 1-based arrays */
                 mod_ptr->gh[ii] = f1;
                 mod_ptr->ghr[ii] = f3;
                 if (m != 0)
                 {
                    ii++;
                    mod_ptr->gh[ii] = f2;
                    mod_ptr->ghr[ii] = f4;
                 }
                 buf[0] = '\0';  /* flag: read a new line */
              }
           }
        }
    }
    fclose(modfile);
    models = (struct model_t **)malloc(nmodels * sizeof(void *));
    if (models == NULL)
    {
        return(-6);
    }
    mod_ptr = first_mod_ptr;
    for (ii=0; ii<nmodels; ii++)
    {
        models[ii] = mod_ptr;
        mod_ptr = mod_ptr->next;
    }
    *model_array = models;
    return nmodels;

    error:
    fclose(modfile);
    /* Clean up by working forward through the linked list. */
    for (ii=0; ii<nmodels; ii++)
    {
        mod_ptr = first_mod_ptr->next;
        if (first_mod_ptr) free(first_mod_ptr);
        first_mod_ptr = mod_ptr;
    }
    return ret;
}

void free_models(struct model_t **model_array, int nmodels)
{
    int i;

    for (i=0; i<nmodels; i++)
    {
        if (model_array[i]) free(model_array[i]);
    }
    if (model_array) free(model_array);
}

int dihf_from_models(struct model_t **model_array, int nmodels,
                        double yr, double lon, double lat,
                        double *d_ptr, double *i_ptr, double *h_ptr,
                        double *f_ptr)
{
    int ret = 0;  /* return code */
    int modelI;
    int nmax;
    double gha[MAXCOEFF];
    double x, y, z;
    double d, i, h, f;
    struct model_t *modI, *modIp;

    /* might not want to keep these */
    int warn_H = 0;
    int warn_H_strong = 0;
    double warn_H_strong_val;


    for (modelI=0; modelI<nmodels; modelI++)
    {
        if (yr < model_array[modelI]->yrmax)
            break;
    }
    if (modelI == nmodels) modelI--;

    modI = model_array[modelI];
    if (modI->max2 == 0)
    {
        modIp = model_array[modelI+1];
        nmax = interpsh(yr, modI->yrmin, modI->max1,
                            modIp->yrmin, modIp->max1,
                            modI->gh, modIp->gh, gha);
    }
    else
    {
        nmax = extrapsh(yr, modI->epoch, modI->max1, modI->max2,
                            modI->gh, modI->ghr, gha);
    }

    shval3(1, lat, lon, 0.0, nmax, gha,
           IEXT, EXT_COEFF1, EXT_COEFF2, EXT_COEFF3,
           &x, &y, &z);
    dihf(x, y, z, &d, &i, &h, &f);

    if (h < 100.0) /* at magnetic poles */
    {
        d = NaN;
        /* while rest is ok */
    }

    if (90.0-fabs(lat) <= 0.001) /* at geographic poles */
    {
        x = NaN;
        y = NaN;
        d = NaN;
        /* while rest is ok */
    }

    *d_ptr = d * (180.0/M_PI);
    *i_ptr = i * (180.0/M_PI);
    *h_ptr = h;
    *f_ptr = f;
    return ret;  /* always 0 at present */
}



/* subroutines below are modifications of the routines from geomag61.c */


/****************************************************************************/
/*                                                                          */
/*                           Subroutine julday                              */
/*                                                                          */
/****************************************************************************/
/*                                                                          */
/*     Computes the decimal day of year from month, day, year.              */
/*     Leap years accounted for 1900 and 2000 are not leap years.           */
/*                                                                          */
/*     Input:                                                               */
/*           year - Integer year of interest                                */
/*           month - Integer month of interest                              */
/*           day - Integer day of interest                                  */
/*                                                                          */
/*     Output:                                                              */
/*           date - Julian date to thousandth of year                       */
/*                                                                          */
/*     FORTRAN                                                              */
/*           S. McLean                                                      */
/*           NGDC, NOAA egc1, 325 Broadway, Boulder CO.  80301              */
/*                                                                          */
/*     C                                                                    */
/*           C. H. Shaffer                                                  */
/*           Lockheed Missiles and Space Company, Sunnyvale CA              */
/*           August 12, 1988                                                */
/*                                                                          */
/*     Julday Bug Fix                                                       */
/*           Thanks to Rob Raper                                            */
/****************************************************************************/


double julday(int i_month, int i_day, int i_year)
{
   int   aggregate_first_day_of_month[13];
   int   leap_year = 0;
   int   truncated_dividend;
   double year;
   double day;
   double decimal_date;
   double remainder = 0.0;
   double divisor = 4.0;
   double dividend;
   double left_over;

   aggregate_first_day_of_month[1] = 1;
   aggregate_first_day_of_month[2] = 32;
   aggregate_first_day_of_month[3] = 60;
   aggregate_first_day_of_month[4] = 91;
   aggregate_first_day_of_month[5] = 121;
   aggregate_first_day_of_month[6] = 152;
   aggregate_first_day_of_month[7] = 182;
   aggregate_first_day_of_month[8] = 213;
   aggregate_first_day_of_month[9] = 244;
   aggregate_first_day_of_month[10] = 274;
   aggregate_first_day_of_month[11] = 305;
   aggregate_first_day_of_month[12] = 335;

   /* Test for leap year.  If true add one to day. */

   year = i_year;                                 /*    Century Years not   */
   if ((i_year != 1900) && (i_year != 2100))      /*  divisible by 400 are  */
   {                                              /*      NOT leap years    */
      dividend = year/divisor;
      truncated_dividend = dividend;
      left_over = dividend - truncated_dividend;
      remainder = left_over*divisor;
      if ((remainder > 0.0) && (i_month > 2))
      {
         leap_year = 1;
      }
      else
      {
         leap_year = 0;
      }
   }
   day = aggregate_first_day_of_month[i_month] + i_day - 1 + leap_year;
   if (leap_year)
   {
      decimal_date = year + (day/366.0);  /*In version 3.0 this was incorrect*/
   }
   else
   {
      decimal_date = year + (day/365.0);  /*In version 3.0 this was incorrect*/
   }
   return(decimal_date);
}


/****************************************************************************/
/*                                                                          */
/*                           Subroutine extrapsh                            */
/*                                                                          */
/****************************************************************************/
/*                                                                          */
/*     Extrapolates linearly a spherical harmonic model with a              */
/*     rate-of-change model.                                                */
/*                                                                          */
/*     Input:                                                               */
/*           date     - date of resulting model (in decimal year)           */
/*           dte1     - date of base model                                  */
/*           nmax1    - maximum degree and order of base model              */
/*           gh1      - Schmidt quasi-normal internal spherical             */
/*                      harmonic coefficients of base model                 */
/*           nmax2    - maximum degree and order of rate-of-change model    */
/*           gh2      - Schmidt quasi-normal internal spherical             */
/*                      harmonic coefficients of rate-of-change model       */
/*                                                                          */
/*     Output:                                                              */
/*           gha or b - Schmidt quasi-normal internal spherical             */
/*                    harmonic coefficients                                 */
/*           nmax   - maximum degree and order of resulting model           */
/*                                                                          */
/*     FORTRAN                                                              */
/*           A. Zunde                                                       */
/*           USGS, MS 964, box 25046 Federal Center, Denver, CO.  80225     */
/*                                                                          */
/*     C                                                                    */
/*           C. H. Shaffer                                                  */
/*           Lockheed Missiles and Space Company, Sunnyvale CA              */
/*           August 16, 1988                                                */
/*                                                                          */
/****************************************************************************/

/* gh_Schmidt[12] are input arrays of Schmidt coefficients: gh1, gh2 */
/* gh_model is an output array of model coefficients: gha or ghb */

int extrapsh(double date, double dte1, int nmax1, int nmax2,
                double *gh_Schmidt1, double *gh_Schmidt2, double *gh_model)
{
   int   nmax;
   int   k, l;
   int   ii;
   double factor;

   factor = date - dte1;
   if (nmax1 == nmax2)
   {
      k =  nmax1 * (nmax1 + 2);
      nmax = nmax1;
   }
   else
   {
      if (nmax1 > nmax2)
      {
         k = nmax2 * (nmax2 + 2);
         l = nmax1 * (nmax1 + 2);
         for ( ii = k + 1; ii <= l; ++ii)
         {
            gh_model[ii] = gh_Schmidt1[ii];
         }
         nmax = nmax1;
      }
      else
      {
         k = nmax1 * (nmax1 + 2);
         l = nmax2 * (nmax2 + 2);
         for ( ii = k + 1; ii <= l; ++ii)
         {
            gh_model[ii] = factor * gh_Schmidt2[ii];
         }
         nmax = nmax2;
      }
   }
   for ( ii = 1; ii <= k; ++ii)
   {
      gh_model[ii] = gh_Schmidt1[ii] + factor * gh_Schmidt2[ii];
   }
   return(nmax);
}

/****************************************************************************/
/*                                                                          */
/*                           Subroutine interpsh                            */
/*                                                                          */
/****************************************************************************/
/*                                                                          */
/*     Interpolates linearly, in time, between two spherical harmonic       */
/*     models.                                                              */
/*                                                                          */
/*     Input:                                                               */
/*           date     - date of resulting model (in decimal year)           */
/*           dte1     - date of earlier model                               */
/*           nmax1    - maximum degree and order of earlier model           */
/*           gh1      - Schmidt quasi-normal internal spherical             */
/*                      harmonic coefficients of earlier model              */
/*           dte2     - date of later model                                 */
/*           nmax2    - maximum degree and order of later model             */
/*           gh2      - Schmidt quasi-normal internal spherical             */
/*                      harmonic coefficients of internal model             */
/*                                                                          */
/*     Output:                                                              */
/*           gha or b - coefficients of resulting model                     */
/*           nmax     - maximum degree and order of resulting model         */
/*                                                                          */
/*     FORTRAN                                                              */
/*           A. Zunde                                                       */
/*           USGS, MS 964, box 25046 Federal Center, Denver, CO.  80225     */
/*                                                                          */
/*     C                                                                    */
/*           C. H. Shaffer                                                  */
/*           Lockheed Missiles and Space Company, Sunnyvale CA              */
/*           August 17, 1988                                                */
/*                                                                          */
/****************************************************************************/

/* gh_Schmidt[12] are input arrays of Schmidt coefficients: gh1, gh2 */
/* gh_model is an output array of model coefficients: gha or ghb */

int interpsh(double date, double dte1, int nmax1, double dte2, double nmax2,
                double *gh_Schmidt1, double *gh_Schmidt2, double *gh_model)
{
   int   nmax;
   int   k, l;
   int   ii;
   double factor;

   factor = (date - dte1) / (dte2 - dte1);
   if (nmax1 == nmax2)
   {
      k =  nmax1 * (nmax1 + 2);
      nmax = nmax1;
   }
   else
   {
      if (nmax1 > nmax2)
      {
         k = nmax2 * (nmax2 + 2);
         l = nmax1 * (nmax1 + 2);
         for ( ii = k + 1; ii <= l; ++ii)
         {
            gh_model[ii] = gh_Schmidt1[ii] * (1 - factor);
         }
         nmax = nmax1;
      }
      else
      {
         k = nmax1 * (nmax1 + 2);
         l = nmax2 * (nmax2 + 2);
         for ( ii = k + 1; ii <= l; ++ii)
         {
            gh_model[ii] = factor * gh_Schmidt2[ii];
         }
         nmax = nmax2;
      }
   }
   for ( ii = 1; ii <= k; ++ii)
   {
      gh_model[ii] = gh_Schmidt1[ii] +
                        factor * (gh_Schmidt2[ii] - gh_Schmidt1[ii]);
   }
   return(nmax);
}





/****************************************************************************/
/*                                                                          */
/*                           Subroutine shval3                              */
/*                                                                          */
/****************************************************************************/
/*                                                                          */
/*     Calculates field components from spherical harmonic (sh)             */
/*     models.                                                              */
/*                                                                          */
/*     Input:                                                               */
/*           igdgc     - indicates coordinate system used; set equal        */
/*                       to 1 if geodetic, 2 if geocentric                  */
/*           latitude  - north latitude, in degrees                         */
/*           longitude - east longitude, in degrees                         */
/*           elev      - WGS84 altitude above mean sea level (igdgc=1), or  */
/*                       radial distance from earth's center (igdgc=2)      */
/*           nmax      - maximum degree and order of coefficients           */
/*           iext      - external coefficients flag (=0 if none)            */
/*           ext1,2,3  - the three 1st-degree external coefficients         */
/*                       (not used if iext = 0)                             */
/*                                                                          */
/*     Output:                                                              */
/*           x         - northward component                                */
/*           y         - eastward component                                 */
/*           z         - vertically-downward component                      */
/*                                                                          */
/*     based on subroutine 'igrf' by D. R. Barraclough and S. R. C. Malin,  */
/*     report no. 71/1, institute of geological sciences, U.K.              */
/*                                                                          */
/*     FORTRAN                                                              */
/*           Norman W. Peddie                                               */
/*           USGS, MS 964, box 25046 Federal Center, Denver, CO.  80225     */
/*                                                                          */
/*     C                                                                    */
/*           C. H. Shaffer                                                  */
/*           Lockheed Missiles and Space Company, Sunnyvale CA              */
/*           August 17, 1988                                                */
/*                                                                          */
/****************************************************************************/


/* gh is the array of model coefficients--gha or ghb */

void shval3(int igdgc, double flat, double flon, double elev,
                int nmax, double *gh, int iext,
                double ext1, double ext2, double ext3,
                double *x_ptr, double *y_ptr, double *z_ptr)
{
   double earths_radius = 6371.2;
   double dtr = 0.01745329;
   double slat;
   double clat;
   double ratio;
   double aa, bb, cc, dd;
   double sd;
   double cd;
   double r;
   double a2;
   double b2;
   double rr;
   double fm,fn;
   double sl[14];
   double cl[14];
   double p[119];
   double q[119];
   int ii,j,k,l,m,n;
   int npq;
   double power;

   double x, y, z;

   /* a2,b2     - squares of semi-major and semi-minor axes of       */
   /*             the reference spheroid used for transforming       */
   /*             between geodetic and geocentric coordinates        */
   /*             or components                                      */
   a2 = 40680631.59;            /* WGS84 */
   b2 = 40408299.98;            /* WGS84 */

   r = elev;
   slat = sin(flat * dtr  );
   if ((90.0 - flat) < 0.001)
   {
      aa = 89.999;            /*  300 ft. from North pole  */
   }
   else
   {
      if ((90.0 + flat) < 0.001)
      {
         aa = -89.999;        /*  300 ft. from South pole  */
      }
      else
      {
         aa = flat;
      }
   }
   clat = cos(aa * dtr);
   sl[1] = sin(flon*dtr);
   cl[1] = cos(flon*dtr);

   x = y = z = 0.0;

   sd = 0.0;
   cd = 1.0;

   l = 1;
   n = 0;
   m = 1;

   npq = (nmax * (nmax + 3)) / 2;

   if (igdgc == 1)
   {
      aa = a2 * clat * clat;
      bb = b2 * slat * slat;
      cc = aa + bb;
      dd = sqrt(cc);
      r = sqrt(elev * (elev + 2.0 * dd) + (a2 * aa + b2 * bb) / cc);
      cd = (elev + dd) / r;
      sd = (a2 - b2) / dd * slat * clat / r;
      aa = slat;
      slat = slat * cd - clat * sd;
      clat = clat * cd + aa * sd;
   }
   ratio = earths_radius / r;

   aa = sqrt(3.0);
   p[1] = 2.0 * slat;
   p[2] = 2.0 * clat;
   p[3] = 4.5 * slat * slat - 1.5;
   p[4] = 3.0 * aa * clat * slat;
   q[1] = -clat;
   q[2] = slat;
   q[3] = -3.0 * clat * slat;
   q[4] = aa * (slat * slat - clat * clat);

   for ( k = 1; k <= npq; ++k)
   {
      if (n < m)
      {
         m = 0;
         n = n + 1;
         power =  n + 2;
         rr = pow(ratio,power);
         fn = n;
      }
      fm = m;
      if (k >= 5)
      {
         if (m == n)
         {
            aa = sqrt(1.0 - 0.5/fm);
            j = k - n - 1;
            p[k] = (1.0 + 1.0/fm) * aa * clat * p[j];
            q[k] = aa * (clat * q[j] + slat/fm * p[j]);
            sl[m] = sl[m-1] * cl[1] + cl[m-1] * sl[1];
            cl[m] = cl[m-1] * cl[1] - sl[m-1] * sl[1];
         }
         else
         {
            aa = sqrt(fn*fn - fm*fm);
            bb = sqrt(((fn - 1.0)*(fn-1.0)) - (fm * fm)) / aa;
            cc = (2.0 * fn - 1.0)/aa;
            ii = k - n;
            j = k - 2 * n + 1;
            p[k] = (fn + 1.0) * (cc * slat/fn * p[ii] - bb/(fn - 1.0) * p[j]);
            q[k] = cc * (slat * q[ii] - clat/fn * p[ii]) - bb * q[j];
         }
      }
      aa = rr * gh[l];
      if (m == 0)
      {
         x = x + aa * q[k];
         z = z - aa * p[k];
         l = l + 1;
      }
      else
      {
         bb = rr * gh[l+1];
         cc = aa * cl[m] + bb * sl[m];
         x = x + cc * q[k];
         z = z - cc * p[k];
         if (clat > 0)
         {
            y = y + (aa * sl[m] - bb * cl[m]) *
                fm * p[k]/((fn + 1.0) * clat);
         }
         else
         {
            y = y + (aa * sl[m] - bb * cl[m]) * q[k] * slat;
         }
         l = l + 2;
      }
      m = m + 1;
   }
   if (iext != 0)
   {
      aa = ext2 * cl[1] + ext3 * sl[1];
      x = x - ext1 * clat + aa * slat;
      y = y + ext2 * sl[1] - ext3 * cl[1];
      z = z + ext1 * slat + aa * clat;
   }
   aa = x;
   x = x * cd + z * sd;
   z = z * cd - aa * sd;

   *x_ptr = x;
   *y_ptr = y;
   *z_ptr = z;
}


/****************************************************************************/
/*                                                                          */
/*                           Subroutine dihf                                */
/*                                                                          */
/****************************************************************************/
/*                                                                          */
/*     Computes the geomagnetic d, i, h, and f from x, y, and z.            */
/*                                                                          */
/*     Input:                                                               */
/*           x  - northward component                                       */
/*           y  - eastward component                                        */
/*           z  - vertically-downward component                             */
/*                                                                          */
/*     Output:                                                              */
/*           d  - declination                                               */
/*           i  - inclination                                               */
/*           h  - horizontal intensity                                      */
/*           f  - total intensity                                           */
/*                                                                          */
/*     FORTRAN                                                              */
/*           A. Zunde                                                       */
/*           USGS, MS 964, box 25046 Federal Center, Denver, CO.  80225     */
/*                                                                          */
/*     C                                                                    */
/*           C. H. Shaffer                                                  */
/*           Lockheed Missiles and Space Company, Sunnyvale CA              */
/*           August 22, 1988                                                */
/*                                                                          */
/****************************************************************************/

void dihf(double x, double y, double z,
                 double *d_ptr, double *i_ptr, double *h_ptr, double *f_ptr)
{
   double d, i, h, f;
   double h2;
   double hpx;
   double sn = 0.0001;  /* constant threshold */

   h2 = x*x + y*y;
   h = sqrt(h2);       /* calculate horizontal intensity */
   f = sqrt(h2 + z*z);      /* calculate total intensity */
   if (f < sn)
   {
      d = NaN;        /* If d and i cannot be determined, */
      i = NaN;        /*       set equal to NaN         */
   }
   else
   {
      i = atan2(z, h);
      if (h < sn)
      {
         d = NaN;
      }
      else
      {
         hpx = h + x;
         if (hpx < sn)
         {
            d = M_PI;
         }
         else
         {
            d = 2.0 * atan2(y, hpx);
         }
      }
   }
   *d_ptr = d;
   *i_ptr = i;
   *h_ptr = h;
   *f_ptr = f;
}

