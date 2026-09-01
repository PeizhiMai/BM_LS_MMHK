#!/bin/bash
set -Eeuo pipefail
[[ $# -eq 3 ]] || { echo "usage: validate_output.sh FILE U V" >&2; exit 64; }
FILE=$1; EXPECT_U=$2; EXPECT_V=$3
[[ -f "$FILE" && ! -L "$FILE" && -s "$FILE" ]] || { echo "missing/not-regular output: $FILE" >&2; exit 65; }
awk -v EU="$EXPECT_U" -v EV="$EXPECT_V" '
function abs(x){return x<0?-x:x}
function closev(x,y,t){s=abs(y); if(s<1)s=1; return abs(x-y)<=t*s}
function numeric(s){return s ~ /^[-+]?(([0-9]+([.][0-9]*)?)|([.][0-9]+))([eE][-+]?[0-9]+)?$/}
function need(k,  x){if(count[k]!=1){print "bad key count " k "=" count[k] > "/dev/stderr"; bad=1; return 0} if(!numeric(raw[k])){print "nonnumeric " k "=" raw[k] > "/dev/stderr"; bad=1; return 0} x=raw[k]+0; if(abs(x)>1e100){print "nonfinite/unbounded " k > "/dev/stderr"; bad=1; return 0}; return x}
{k=$1; v=$2; if(k=="status"){status_count++; status=v} if(k=="Q"){q_count++; q=v} if(k=="Lx"||k=="Ly"||k=="tp"||k=="U"||k=="V"||k=="E0"||k=="<nn_NN>"||k=="<delta_n_delta_n_NN>"||k=="<Kinetic_NN_per_site>"||k=="<Kinetic_NNN_per_site>"||k=="<Kinetic_per_site>"||k=="<C1_NN>"||k=="<ni_upni_dn>"||k=="<Sc_pipi>"||k=="<mCDW2_pipi>"){count[k]++; raw[k]=v}}
END{if(status_count!=1||status!="COMPLETE"){print "missing/nonunique COMPLETE status" > "/dev/stderr"; bad=1} if(q_count!=1||q!="0,0"){print "bad/nonunique Q=" q > "/dev/stderr"; bad=1} Lx=need("Lx"); Ly=need("Ly"); tp=need("tp"); U=need("U"); V=need("V"); E0=need("E0"); nn=need("<nn_NN>"); dnn=need("<delta_n_delta_n_NN>"); knn=need("<Kinetic_NN_per_site>"); knnn=need("<Kinetic_NNN_per_site>"); kt=need("<Kinetic_per_site>"); cnn=need("<C1_NN>"); D=need("<ni_upni_dn>"); Sc=need("<Sc_pipi>"); mc=need("<mCDW2_pipi>"); if(!closev(Lx,4,1e-10)||!closev(Ly,4,1e-10)||!closev(tp,0,1e-10)||!closev(U,EU+0,1e-10)||!closev(V,EV+0,1e-10)){print "metadata mismatch" > "/dev/stderr"; bad=1} r1=E0/16-(kt+U*D+2*V*nn); r2=dnn-(nn-1); r3=kt-(knn+knnn); r4=mc-Sc/16; if(abs(r1)>1e-8||abs(r2)>1e-8||abs(r3)>1e-8||abs(r4)>1e-8){printf "identity residuals %.17g %.17g %.17g %.17g\n",r1,r2,r3,r4 > "/dev/stderr"; bad=1} if(cnn < -0.75000001 || cnn > 0.25000001){print "C_NN out of bounds" > "/dev/stderr"; bad=1} if(D<0 || D>1 || mc<0 || mc>1){print "physical bounds failed" > "/dev/stderr"; bad=1} if(bad)exit 2; printf "VALID identities=%.3e,%.3e,%.3e,%.3e C_NN=%.17g D=%.17g mCDW2=%.17g\n",r1,r2,r3,r4,cnn,D,mc}' "$FILE"
