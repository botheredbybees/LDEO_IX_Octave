#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

/* The following include file must define a function 'isnan' */
/* This function, which returns '1' if the number is NaN and 0*/
/* otherwise, could be hand-written if not available. */
/* Comment out one of the two following lines, as applicable */
#include <math.h>               /* for gcc */
/* #include <mathimf.h>            /\* for Intel icc *\/ */

#define NaN log(-1.0)

#define IEXT 0
#define FALSE 0
#define TRUE 1                  /* constants */
#define RECL 81

#define MAXINBUFF RECL+14

/** Max size of in buffer **/

#define MAXREAD MAXINBUFF-2
/** Max to read 2 less than total size (just to be safe) **/

#define MAXMOD 30
/** Max number of models in a file **/

#define PATH MAXREAD
/** Max path and filename length **/

#define EXT_COEFF1 (double)0
#define EXT_COEFF2 (double)0
#define EXT_COEFF3 (double)0

#define MAXDEG 13
#define MAXCOEFF (MAXDEG*(MAXDEG+2)+1)
                /* index starts with 1!, (from old Fortran) */

#define RECLEN 80 /* characters excluding line ending(s) */
#define MAXMODNAMELENGTH 8
                /* e.g. IGRF2005 */

struct model_t{
    char name[MAXMODNAMELENGTH + 1];
    double epoch;
    int max1;
    int max2;
    int max3;
    double yrmin;
    double yrmax;
    double altmin;
    double altmax;
    double gh[MAXCOEFF];  /* first pair of coeffients */
    double ghr[MAXCOEFF]; /* second pair; usually 0; rates of change */
    struct model_t *next;
};


/*  Subroutines used  */

void print_dashed_line();
void print_long_dashed_line(void);
void print_header();
void print_result(double date, double d, double i, double h, double x, double y, double z, double f);
void print_header_sv();
void print_result_sv(double date, double ddot, double idot, double hdot, double xdot, double ydot, double zdot, double fdot);
void print_result_file(FILE *outf, double d, double i, double h, double x, double y, double z, double f,
                       double ddot, double idot, double hdot, double xdot, double ydot, double zdot, double fdot);
double degrees_to_decimal(int degrees,int minutes,int seconds);
double julday(int i_month, int i_day, int i_year);
int interpsh(double date, double dte1, int nmax1, double dte2, double nmax2,
                double *gh_Schmidt1, double *gh_Schmidt2, double *gh_model);
int extrapsh(double date, double dte1, int nmax1, int nmax2,
                double *gh_Schmidt1, double *gh_Schmidt2, double *gh_model);
void shval3(int igdgc, double flat, double flon, double elev,
                int nmax, double *gh, int iext,
                double ext1, double ext2, double ext3,
                double *x_ptr, double *y_ptr, double *z_ptr);
int   safegets(char *buffer,int n);
int getshc(char *file, int iflag, long strec, int nmax_of_gh,
                    double *gh_Schmidt);

void dihf(double x, double y, double z,
                 double *d_ptr, double *i_ptr, double *h_ptr, double *f_ptr);

int models_from_lines(struct model_t ***model_array);
int models_from_file(char *filename, struct model_t ***model_array);
void free_models(struct model_t **model_array, int nmodels);
int dihf_from_models(struct model_t **model_array, int nmodels,
                        double yr, double lon, double lat,
                        double *d_ptr, double *i_ptr, double *h_ptr,
                        double *f_ptr);


