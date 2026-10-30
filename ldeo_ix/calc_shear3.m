function [ds,p,dr] = calc_shear3(d,p,ps,dr)
% function [ds,p,dr] = calc_shear3(d,p,ps,dr)
%
% - compute shear profiles 
% - use only central difference
% - use 2*std editing
% 
% version 8  last change 06.08.2019

%  Martin Visbeck, LDEO, 3/7/97
% some modifications and code cleanup                          GK, 16.05.2015  2-->3
% reinstated the use of d.weight for the identification of shear pairs
%                                                              GK, 03.12.2018  3-->4 
% reorganization of the dz handling                            GK, 12.12.2018  4-->5
% added error output, catch different shear methods            GK, 22.07.2019  5-->6
% more text output                                             
% added new parameter  ps.shear_throw_out_percent              GK, 05.08.2019  6-->7
% fixed bug in shear calculation                               GK, 06.08.2019  7-->8

%======================================================================
%                    C A L C _ S H E A R 3 . M 
%                    doc: Thu Sep  5 10:58:55 2019
%                    dlm: Thu Sep  5 16:27:19 2019
%                    (c) 2019 G. Krahmann
%                    uE-Info: 31 1 NIL 0 0 72 0 2 4 NIL ofnI
%======================================================================

% CHANGES BY ANT:
%	Sep  5, 2019: - added local_weight to another case in if
%				  - added defaults provided by Gerd
%				  - removed 'messages' variable
%				  - replaced all "replace" statements (required 
%				    removal of warning)
%				  - added nmin() nmax() nmean() nstd()
%				  - disabled code (replaced if 0 by if 1) calling
%				  	meanoutlier

% Defaults from Gerd (email 9/5/2019):

% average over data within how many standard deviations from median
% this is the value used by the old calc_shear2.m
% In calc_shear3.m the outlying fraction of data is discarded. Assuming a
% normal distribution a value of stdf=2 converts to an outlier fraction of
% 5%, stdf=3 converts to 1% and stdf=1 converts to 32%.
% Internally in calc_shear3 this is converted so that shear_stdf does not
% need to be changed.
ps.shear_stdf = 2;


% the minimum weight a bin must have to be accepted for shear
ps.shear_weightmin = nan;


% this one is similar to shear_weight_min, but gives the percentage of
% values thrown out. The routine throws out the xx% values with the
% lowest weight. The weights are the correlation based ones.
ps.shear_throw_out_percent = 10;


%
% general function info
%
disp(' ')
disp(['CALC_SHEAR3:  calculate a baroclinic velocity profile based on shears only'])


%
% decide whether central differences or simple differences are to be used in
% the shear calculation
%
% 1: simple differences
% 2: central differences
%
diff_type = 2;


%
% resolution of final shear profile in meter
%
dz = ps.dz;
shear_dz = dz * diff_type;
disp(['    Averaging shear profile over ',num2str(shear_dz),' m intervals'])


%
% Discard a certain amount of data as suspected outliers that
% for relatively small numbers of values will skew the mean.
% In the old calc_shear2.m the allowed range was the std of the shears 
% times the set factor stdf. Default was stdf=2 .
% In calc_shear3.m the outlier determination is iterative and thus a bit
% safer in calculation. The allowed range is set as a fraction of the whole
% population. For gaussian distributions stdf converts to this fraction.
% As usually stdf is not varied much, we have implemented a lookup list
% here.
%
use_new_outlier = 1;
stdf = ps.shear_stdf;
if use_new_outlier==1
  fracs = 1 - [31.8,13.4,4.5,1.3,0.3]/100;
  stdfs = [1,1.5,2,2.5,3];
  [dummy,ind] = min(abs(stdf-stdfs));
  frac = fracs(ind);
end
disp(['    Maximum allowed std within calculation intervals : ',num2str(stdf)])
disp(['    Data deviating more from the median will be discarded.'])


%
% check if only one istrument is to be used
%
if ps.up_dn_looker==2
  % down looker only
  d.weight(d.izu,:)=nan;
elseif ps.up_dn_looker==3
  % up looker only
  d.weight(d.izd,:)=nan;
end


%
% Apply a weight threshold to shear data.
%
% There are two variants.
% First one is used when ps.shear_throw_out_percent is not NaN.
%   This one throws out the xx% shears with the lowest correlation-derived weights.
% Second one is used when ps.shear_weightmin is not NaN.
%   This one sets a minimum weight to keep the shears.
%
% First one is now default with 10%.
%
disp(['    Correlation-derived weights range from ',num2str(nmin(d.weight(:))),' to ',num2str(nmax(d.weight(:)))])
if ~isnan(ps.shear_throw_out_percent)
  local_weight = d.weight;
  ind = find(isfinite(local_weight));
  [dummy,ind2] = sort(local_weight(ind));
  if length(ind2)>9
    local_weight(ind(ind2(1:floor(length(ind2)/10)))) = nan;
  end
elseif ~isnan(ps.shear_weightmin)
  disp(['    Minimum weight  ',num2str(ps.shear_weightmin),' for data to be used in shear calc.'])
  local_weight = double(d.weight>ps.shear_weightmin);
else
  disp('>   No weight criterion applied to raw shear data.')
  disp('>   You should set  ps.shear_throw_out_percent  or  ps.shear_weightmin')
  local_weight = d.weight;
end
disp(['    Removed ',int2str(100-sum(isfinite(local_weight))/sum(isfinite(d.weight))*100),...
  ' % of data with lowest weights from shear calculation.'])
disp(['    New weights range from ',num2str(nmin(local_weight(:))),' to ',num2str(nmax(local_weight(:)))])


%
% convert the weights to 1 and NaN
%
local_weight(find(local_weight <= 0)) = nan;
local_weight(find(local_weight > 0))  = 1;

%
% compute shear
%
% two ways are offered here
% first:   central differences for the shears
% second:  single differences 
% the first is similar to the ways of the old calc_shear2.m
%
% central differences
if diff_type==2
  local_weight = [repmat(nan,1,size(local_weight,2));diff2(local_weight)+1;repmat(nan,1,size(local_weight,2))];
  ushear = [NaN*d.ru(1,:);diff2(d.ru(:,:))./diff2(d.izm);NaN*d.ru(1,:)].*local_weight;
  vshear = [NaN*d.rv(1,:);diff2(d.rv(:,:))./diff2(d.izm);NaN*d.rv(1,:)].*local_weight;
  wshear = [NaN*d.rw(1,:);diff2(d.rw(:,:))./diff2(d.izm);NaN*d.rw(1,:)].*local_weight;
  zshear = -d.izm;
% single differences
else
  ushear = diff( d.ru.*local_weight )./diff(d.izm);
  vshear = diff( d.rv.*local_weight )./diff(d.izm);
  wshear = diff( d.rw.*local_weight )./diff(d.izm);
  zshear = -(d.izm(1:end-1,:)+d.izm(2:end,:))/2;
end
ds.ushear = ushear;
ds.vshear = vshear;
ds.wshear = wshear;
ds.zshear = zshear;


%
% set depth levels
%
z = dr.z;


%
% prepare shear solution result vectors
%
ds.usm = repmat(nan,length(z),1);
ds.vsm = ds.usm;
ds.wsm = ds.usm;
ds.usmd = ds.usm;
ds.vsmd = ds.usm;
ds.use = ds.usm;
ds.vse = ds.usm;
ds.wse = ds.usm;
ds.nn = ds.usm;
ds.z = z;


%
% loop over depth levels and calculate the average shear at that level
%
% in the case of central differences this is oversampled here
% but by sticking with the same resolution it makes the results easier
% to work with
%
for n=[1:length(z)]

  i1 = find( ( abs( zshear - z(n) ) <= shear_dz/2 ) & isfinite( ushear + vshear ) );
  ds.nn(n) = length(i1);
  if ds.nn(n) > 2

    % two ways to select outliers
    % first:   select all that are beyond a fixed range around the median
    % second:  iteratively reject the worst (largest distance from mean)
    %          until a fixed fraction is rejected
    % the second is usually the safer calculation but is a bit slower
    if 1
      usmm = median( ushear(i1) );
      ussd1 = std( ushear(i1) );
      vsmm = median( vshear(i1) );
      vssd1 = std( vshear(i1) );
      wsmm = median( wshear(i1) );
      wssd1 = std( wshear(i1) );
      ii1 = i1( find(abs(ushear(i1)-usmm)<stdf*ussd1) );
      ii2 = i1( find(abs(vshear(i1)-vsmm)<stdf*vssd1) );
      ii3 = i1( find(abs(wshear(i1)-wsmm)<stdf*wssd1) );
    else
      [dummy,ii1] = meanoutlier(ushear(i1),frac);
      [dummy,ii2] = meanoutlier(vshear(i1),frac);
      [dummy,ii3] = meanoutlier(wshear(i1),frac);
      ii1 = i1(ii1);
      ii2 = i1(ii2);
      ii3 = i1(ii3);
    end

    % two ways of calculating the mean and std of the selected shears
    % first:  if there is a rejected one in any of u,v,w shears then use it
    %         for non of the calculations
    % second: if there is a rejected one in any of u,v,w shears then use it
    %         only in u,v or w calculations
    % the second one is the one used by the old calc_shear2.m
    % but to me this does not make sense, GK May 2015
    if 1
      dummy = zeros(size(ushear));
      dummy(ii1) = 1;
      dummy(ii2) = dummy(ii2)+1;
      dummy(ii3) = dummy(ii3)+1;
      ii = find(dummy==3);
      if length(ii)>1

        ds.usm(n) = mean(ushear(ii));
        ds.usmd(n) = median(ushear(ii));
        ds.use(n) = std(ushear(ii));
        ds.ii(n) = length(ii);

        ds.vsm(n) = mean(vshear(ii));
        ds.vsmd(n) = median(vshear(ii));
        ds.vse(n) = std(vshear(ii));

        ds.wsm(n) = mean(wshear(ii));
        ds.wsmd(n) = median(wshear(ii));
        ds.wse(n) = std(wshear(ii));
       
        % debugging plot 
        if 0
          figure(3)
          clf
          subplot(3,1,1)
          hist(ushear(ii),30)
          hold on
          ax = axis;
          plot([1,1]*mean(ushear(ii)),ax(3:4),'r')
          plot([1,1]*median(ushear(ii)),ax(3:4),'m')
          ind = find(dr.z==z(n));
          if ind<length(dr.u)
            plot([1,1]*(dr.u(ind-1)-dr.u(ind+1))/20,ax(3:4),'g')
          end
          title(int2str(z(n)))
          subplot(3,1,2)
          hist(vshear(ii),30)
          hold on
          ax = axis;
          plot([1,1]*mean(vshear(ii)),ax(3:4),'r')
          plot([1,1]*median(vshear(ii)),ax(3:4),'m')
          ind = find(dr.z==z(n));
          if ind<length(dr.u)
            plot([1,1]*(dr.v(ind-1)-dr.v(ind+1))/20,ax(3:4),'g')
          end
          subplot(3,1,3)
          hist( zshear(ii)-z(n), 30 )
          pause
        end 

      end
    else
      if length(ii1)>1
        ds.usm(n) = mean(ushear(ii1));
        ds.usmd(n) = median(ushear(ii1));
        ds.use(n) = std(ushear(ii1));
      end
      if length(ii2)>1
        ds.vsm(n) = mean(vshear(ii2));
        ds.vsmd(n) = median(vshear(ii2));
        ds.vse(n) = std(vshear(ii2));
      end
      if length(ii3)>1
        ds.wsm(n) = mean(wshear(ii3));
        ds.wsmd(n) = median(wshear(ii3));
        ds.wse(n) = nstd(wshear(ii3));
      end
    end
  end

end


%
% a debugging figure
%
if 0
sfigure(3);
clf
orient tall
subplot(1,2,1)
plot(ushear,zshear,'b.','markersize',3)
hold on
plot(ds.usm,ds.z,'r')
plot(ds.usmd,ds.z,'k')
inv_shear_u = -diff(dr.u-mean(dr.u))/dz;
plot(inv_shear_u,(z(1:end-1)+z(2:end))/2,'g')
set(gca,'ydir','reverse')

subplot(1,2,2)
plot(vshear,zshear,'b.','markersize',3)
hold on
plot(ds.vsm,ds.z,'r')
plot(ds.vsmd,ds.z,'k')
inv_shear_v = -diff(dr.v-mean(dr.v))/dz;
plot(inv_shear_v,(z(1:end-1)+z(2:end))/2,'g')
set(gca,'ydir','reverse')

sfigure(2)
end



%
% integrate shear profile (from bottom up)
%
ds.usm(find(isnan(ds.usm))) = 0;
ds.vsm(find(isnan(ds.vsm))) = 0;
ds.wsm(find(isnan(ds.wsm))) = 0;
%if length(ind)/length(ds.usm)*100>5
%  disp(['>   Found ',num2str(length(ind)/length(ds.usm)*100),...
%    '% Nan in shear data. Integration result might be problematic.'])
%end
if 1
  ds.ur = flipud(cumsum(flipud(ds.usm)))*dz;
  ds.vr = flipud(cumsum(flipud(ds.vsm)))*dz;
  ds.wr = flipud(cumsum(flipud(ds.wsm)))*dz;
else
  ds.ur = flipud(cumsum(flipud(ds.usmd)))*dz;
  ds.vr = flipud(cumsum(flipud(ds.vsmd)))*dz;
  ds.wr = flipud(cumsum(flipud(ds.wsmd)))*dz;
end
ds.ur = ds.ur-mean(ds.ur);
ds.vr = ds.vr-mean(ds.vr);
ds.wr = ds.wr-mean(ds.wr);


%
% This is a peculiar place for the single ping error estimate. But 
% as it is based on the variability in the data itself, it makes sense.
% The assumption is that there should be basically zero shear in the
% vertical velocities. At least it is so small as to be not detectable
% here. Thus any variability in the vertical shear is caused by the
% errors/noise of the measurement. Together with an angular conversion
% factor this gives an error/noise value for the horizontal velocities.
%
if ~isfield(d,'zd')
  dz2 = abs(nmean(diff(d.z)));
else
  dz2 = diff_type*abs(mean(diff(d.zd)));
end
if isfield(d,'down')
  fac = 1/tan(d.down.Beam_angle*pi/180)*sqrt(2)*dz2;
else
  fac = 1/tan(d.up.Beam_angle*pi/180)*sqrt(2)*dz2;
end
ds.ensemble_vel_err = ds.wse*fac;
dr.ensemble_vel_err = ds.wse*fac;


%
% store result and give text output
%
dr.u_shear_method = ds.ur;
dr.v_shear_method = ds.vr;
dr.w_shear_method = ds.wr;
uds = nstd(dr.u-mean(dr.u)-ds.ur);
vds = nstd(dr.v-mean(dr.v)-ds.vr);
uvds = sqrt(uds^2+vds^2);
disp(['    Inversion average error : ',num2str(nmean( dr.uerr ) ),' m/s'])
if uvds>nmean(dr.uerr)*1.5
  error_increase_factor = 1/nmean(dr.uerr)*uvds/1.5;
  warn = ('>   Increasing error estimate because of elevated shear - inverse difference');
  disp(warn)
  disp(['>   by a factor of ',num2str(error_increase_factor)])
  disp(['>   std of difference between regular and shear profile : ',num2str(uvds),' m/s'])
  p.warnp(size(p.warnp,1)+1,1:length(warn))=warn;
  dr.uerr = dr.uerr * error_increase_factor;
end
disp(['    Final average error : ',num2str(nmean( dr.uerr ) ),' m/s'])

%--------------------------------------------------

function x = diff2(x,k,dn)
%DIFF2   Difference function.  If X is a vector [x(1) x(2) ... x(n)],
%       then DIFF(X) returns a vector of central differences between
%       elements [x(3)-x(1)  x(4)-x(2) ... x(n)-x(n-2)].  If X is a
%	matrix, the differences are calculated down each column:
%       DIFF(X) = X(3:n,:) - X(1:n-2,:).
%	DIFF(X,n) is the n'th difference function.

%	J.N. Little 8-30-85
%	Copyright (c) 1985, 1986 by the MathWorks, Inc.

if nargin < 2,	k = 1; end
if nargin < 3,	dn = 2; end
for i=1:k
	[m,n] = size(x);
	if m == 1
                x = x(1+dn:n) - x(1:n-dn);
	else
                x = x(1+dn:m,:) - x(1:m-dn,:);
	end
end

%----------------------------------------------------------------------

function m = nmin(d)
	m = min(d(find(isfinite(d))));

function m = nmax(d)
	m = max(d(find(isfinite(d))));

function m = nmean(d)
	m = mean(d(find(isfinite(d))));

function m = nstd(d)
	m = std(d(find(isfinite(d))));



