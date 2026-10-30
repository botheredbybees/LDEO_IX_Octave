function [B, idx] = rmmissing(A, dim)
% rmmissing  Remove rows (dim=1, the default) or columns (dim=2) of a numeric
% matrix that contain NaN.
%
% Stand-in for MATLAB's rmmissing (R2016b), which Octave 9 does not implement.
% Only the numeric-matrix subset LDEO_IX uses is provided: loadctd.m calls
% rmmissing(A,2). Cell arrays, tables, the "MissingLocations" option and
% the NaN-in-strings cases are not supported.
%
% Original code written for this project (MIT, see LICENSE).
  if nargin < 2
    dim = 1;
  end
  if ~isnumeric(A) && ~islogical(A)
    error('rmmissing stub: only numeric arrays are supported');
  end
  if dim == 1
    idx = any(isnan(A), 2);
    B = A(~idx, :);
  elseif dim == 2
    idx = any(isnan(A), 1);
    B = A(:, ~idx);
  else
    error('rmmissing stub: dim must be 1 or 2');
  end
end
