#include <cassert>
#include <cmath>
#include <complex>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "qbasis.h"

#define PI 3.141592653589793238462643383279502884

namespace {

std::string format_parameter(const double value) {
    std::ostringstream stream;
    stream << std::defaultfloat << std::setprecision(8) << value;
    return stream.str();
}

}  // namespace

// Ground-state-only V-extended 16-MMHK solver.  The Hamiltonian and fixed
// (N_up,N_down,Q) basis are identical to Hubbard_sym_testobs_UV.cc, but this
// executable measures only E0 and the site-averaged double occupancy.
int main(int argc, char* argv[]) {
    if (argc < 10) {
        std::cerr << "Usage: " << argv[0]
                  << " N_up N_dn kx ky qx qy U V tp [seed]" << std::endl;
        return 1;
    }

    const int Nup_input = std::atoi(argv[1]);
    const int Ndn_input = std::atoi(argv[2]);
    const int kx = std::atoi(argv[3]);
    const int ky = std::atoi(argv[4]);
    const int Qm = std::atoi(argv[5]);
    const int Qn = std::atoi(argv[6]);
    const double U = std::atof(argv[7]);
    const double V = std::atof(argv[8]);
    const double tp = std::atof(argv[9]);
    const unsigned int seed = (argc >= 11)
                                  ? static_cast<unsigned int>(std::strtoul(argv[10], nullptr, 10))
                                  : 1U;
    std::srand(seed);

    qbasis::initialize();
    std::cout << std::setprecision(12);

    constexpr double t = 1.0;
    constexpr int Lx = 4;
    constexpr int Ly = 4;
    constexpr int Nsites_int = Lx * Ly;
    constexpr MKL_INT max_iterations = 10000;
    const double Nup_total = static_cast<double>(Nup_input);
    const double Ndn_total = static_cast<double>(Ndn_input);
    const double Ntotal_value = Nup_total + Ndn_total;

    // Keep the same infinitesimal offset used by the production observable
    // executable so validation can be performed bit-for-bit at a fixed grid
    // point.
    const double fx = kx * PI / 40.0 + 0.00001;
    const double fy = ky * PI / 40.0 + 0.00001;
    const double sx = std::sin(fx);
    const double cx = std::cos(fx);
    const double sy = std::sin(fy);
    const double cy = std::cos(fy);
    const double cxpy = std::cos(fx + fy);
    const double sxpy = std::sin(fx + fy);
    const double cxmy = std::cos(fx - fy);
    const double sxmy = std::sin(fx - fy);

    std::cout << "Lx =      " << Lx << '\n'
              << "Ly =      " << Ly << '\n'
              << "t =       " << t << '\n'
              << "tp =      " << tp << '\n'
              << "U =       " << U << '\n'
              << "V =       " << V << '\n'
              << "kx =      " << kx << '\n'
              << "ky =      " << ky << '\n'
              << "Qx =      " << Qm << '\n'
              << "Qy =      " << Qn << '\n'
              << "N_up =    " << Nup_total << '\n'
              << "N_dn =    " << Ndn_total << '\n'
              << "seed =    " << seed << '\n'
              << "maxit =   " << max_iterations << std::endl;

    std::vector<std::string> bc{"pbc", "pbc"};
    qbasis::lattice lattice(
        "square", {static_cast<uint32_t>(Lx), static_cast<uint32_t>(Ly)}, bc);

    auto c_up = std::vector<std::vector<std::complex<double>>>(
        4, std::vector<std::complex<double>>(4, 0.0));
    auto c_dn = std::vector<std::vector<std::complex<double>>>(
        4, std::vector<std::complex<double>>(4, 0.0));
    c_up[0][1] = std::complex<double>(1.0, 0.0);
    c_up[2][3] = std::complex<double>(1.0, 0.0);
    c_dn[0][2] = std::complex<double>(1.0, 0.0);
    c_dn[1][3] = std::complex<double>(-1.0, 0.0);

    qbasis::model<std::complex<double>> Hubbard(lattice);
    Hubbard.add_orbital(lattice.Nsites, "electron");
    qbasis::mopr<std::complex<double>> Nup;
    qbasis::mopr<std::complex<double>> Ndown;
    qbasis::mopr<std::complex<double>> double_occupancy_sum;

    for (int x = 0; x < Lx; ++x) {
        for (int y = 0; y < Ly; ++y) {
            uint32_t site_i;
            uint32_t site_j;
            std::vector<int> work(lattice.dim);
            lattice.coor2site({x, y}, 0, site_i, work);

            auto c_up_i = qbasis::opr<std::complex<double>>(site_i, 0, true, c_up);
            auto c_dn_i = qbasis::opr<std::complex<double>>(site_i, 0, true, c_dn);
            auto c_up_dg_i = c_up_i;
            auto c_dn_dg_i = c_dn_i;
            c_up_dg_i.dagger();
            c_dn_dg_i.dagger();
            auto n_up_i = c_up_dg_i * c_up_i;
            auto n_dn_i = c_dn_dg_i * c_dn_i;
            auto n_i = n_up_i + n_dn_i;

            lattice.coor2site({x + 1, y}, 0, site_j, work);
            auto c_up_jx = qbasis::opr<std::complex<double>>(site_j, 0, true, c_up);
            auto c_dn_jx = qbasis::opr<std::complex<double>>(site_j, 0, true, c_dn);
            auto c_up_dg_jx = c_up_jx;
            auto c_dn_dg_jx = c_dn_jx;
            c_up_dg_jx.dagger();
            c_dn_dg_jx.dagger();
            auto n_jx = c_up_dg_jx * c_up_jx + c_dn_dg_jx * c_dn_jx;

            Hubbard.add_Ham(std::complex<double>(-t * cx, -t * sx) * (c_up_dg_i * c_up_jx));
            Hubbard.add_Ham(std::complex<double>(-t * cx, t * sx) * (c_up_dg_jx * c_up_i));
            Hubbard.add_Ham(std::complex<double>(-t * cx, -t * sx) * (c_dn_dg_i * c_dn_jx));
            Hubbard.add_Ham(std::complex<double>(-t * cx, t * sx) * (c_dn_dg_jx * c_dn_i));
            Hubbard.add_Ham(std::complex<double>(V, 0.0) * (n_i * n_jx));

            lattice.coor2site({x, y + 1}, 0, site_j, work);
            auto c_up_jy = qbasis::opr<std::complex<double>>(site_j, 0, true, c_up);
            auto c_dn_jy = qbasis::opr<std::complex<double>>(site_j, 0, true, c_dn);
            auto c_up_dg_jy = c_up_jy;
            auto c_dn_dg_jy = c_dn_jy;
            c_up_dg_jy.dagger();
            c_dn_dg_jy.dagger();
            auto n_jy = c_up_dg_jy * c_up_jy + c_dn_dg_jy * c_dn_jy;

            Hubbard.add_Ham(std::complex<double>(-t * cy, -t * sy) * (c_up_dg_i * c_up_jy));
            Hubbard.add_Ham(std::complex<double>(-t * cy, t * sy) * (c_up_dg_jy * c_up_i));
            Hubbard.add_Ham(std::complex<double>(-t * cy, -t * sy) * (c_dn_dg_i * c_dn_jy));
            Hubbard.add_Ham(std::complex<double>(-t * cy, t * sy) * (c_dn_dg_jy * c_dn_i));
            Hubbard.add_Ham(std::complex<double>(V, 0.0) * (n_i * n_jy));

            lattice.coor2site({x + 1, y + 1}, 0, site_j, work);
            auto c_up_jpp = qbasis::opr<std::complex<double>>(site_j, 0, true, c_up);
            auto c_dn_jpp = qbasis::opr<std::complex<double>>(site_j, 0, true, c_dn);
            auto c_up_dg_jpp = c_up_jpp;
            auto c_dn_dg_jpp = c_dn_jpp;
            c_up_dg_jpp.dagger();
            c_dn_dg_jpp.dagger();
            Hubbard.add_Ham(std::complex<double>(-tp * cxpy, -tp * sxpy) * (c_up_dg_i * c_up_jpp));
            Hubbard.add_Ham(std::complex<double>(-tp * cxpy, tp * sxpy) * (c_up_dg_jpp * c_up_i));
            Hubbard.add_Ham(std::complex<double>(-tp * cxpy, -tp * sxpy) * (c_dn_dg_i * c_dn_jpp));
            Hubbard.add_Ham(std::complex<double>(-tp * cxpy, tp * sxpy) * (c_dn_dg_jpp * c_dn_i));

            lattice.coor2site({x + 1, y - 1}, 0, site_j, work);
            auto c_up_jpm = qbasis::opr<std::complex<double>>(site_j, 0, true, c_up);
            auto c_dn_jpm = qbasis::opr<std::complex<double>>(site_j, 0, true, c_dn);
            auto c_up_dg_jpm = c_up_jpm;
            auto c_dn_dg_jpm = c_dn_jpm;
            c_up_dg_jpm.dagger();
            c_dn_dg_jpm.dagger();
            Hubbard.add_Ham(std::complex<double>(-tp * cxmy, -tp * sxmy) * (c_up_dg_i * c_up_jpm));
            Hubbard.add_Ham(std::complex<double>(-tp * cxmy, tp * sxmy) * (c_up_dg_jpm * c_up_i));
            Hubbard.add_Ham(std::complex<double>(-tp * cxmy, -tp * sxmy) * (c_dn_dg_i * c_dn_jpm));
            Hubbard.add_Ham(std::complex<double>(-tp * cxmy, tp * sxmy) * (c_dn_dg_jpm * c_dn_i));

            Hubbard.add_Ham(std::complex<double>(U, 0.0) * (n_up_i * n_dn_i));
            double_occupancy_sum += n_up_i * n_dn_i;
            Nup += n_up_i;
            Ndown += n_dn_i;
        }
    }

    double_occupancy_sum.simplify();
    auto Ntotal = Nup + Ndown;
    Ntotal.simplify();

    Hubbard.fill_Weisse_table();
    Hubbard.enumerate_basis_repr(
        {Qm, Qn}, {Nup, Ndown}, {Nup_total, Ndn_total});
    Hubbard.generate_Ham_sparse_repr();
    Hubbard.locate_E0_lanczos(qbasis::which_sym::repr, 1, 1, max_iterations);

    const MKL_INT which_col = 0;
    std::vector<std::complex<double>> vec_number(Hubbard.dim_repr[0]);
    std::vector<std::complex<double>> vec_double(Hubbard.dim_repr[0]);
    Hubbard.moprXvec_repr(Ntotal, 0, 0, which_col, vec_number.data());
    Hubbard.moprXvec_repr(double_occupancy_sum, 0, 0, which_col, vec_double.data());

    std::complex<double> numerator = 0.0;
    for (MKL_INT index = 0; index < Hubbard.dim_repr[0]; ++index) {
        numerator += std::conj(vec_number[index]) * vec_double[index];
    }
    const double D_eigenvector = std::real(numerator) / (Ntotal_value * Nsites_int);
    // At U=V=tp=0 the half-filled one-body spectrum contains exact shell
    // degeneracies at several mixed-momentum points.  Lanczos may return an
    // arbitrary spin-entangled vector from that degenerate manifold, for which
    // a nonlinear observable such as D is basis dependent.  The physical
    // decoupled-spin free-fermion state factorizes and has
    // <n_up><n_down>=(N_up/N)(N_down/N)=1/4.  Record the raw eigenvector value
    // as well as this degeneracy-resolved free limit.
    const bool factorized_free_limit =
        std::abs(U) < 1.0e-14 && std::abs(V) < 1.0e-14 && std::abs(tp) < 1.0e-14;
    const double D = factorized_free_limit
                         ? (Nup_total / Nsites_int) * (Ndn_total / Nsites_int)
                         : D_eigenvector;
    const double E0 = Hubbard.energy_min();

    const std::string output_name =
        "L" + std::to_string(Lx) + "x" + std::to_string(Ly) +
        "Nup" + std::to_string(Nup_input) + "Ndn" + std::to_string(Ndn_input) +
        "U" + format_parameter(U) + "V" + format_parameter(V) +
        "tp" + format_parameter(tp) + "f" + std::to_string(kx) + "x" +
        std::to_string(ky) + "Q" + std::to_string(Qm) + "x" +
        std::to_string(Qn) + "_E0D.dat";

    std::ofstream output(output_name, std::ios::out);
    output << std::scientific << std::setprecision(18);
    output << "Lx\t" << Lx << '\n';
    output << "Ly\t" << Ly << '\n';
    output << "Nup\t" << Nup_input << '\n';
    output << "Ndn\t" << Ndn_input << '\n';
    output << "tp\t" << tp << '\n';
    output << "U\t" << U << '\n';
    output << "V\t" << V << '\n';
    output << "kx\t" << kx << '\n';
    output << "ky\t" << ky << '\n';
    output << "Qx\t" << Qm << '\n';
    output << "Qy\t" << Qn << '\n';
    output << "seed\t" << seed << '\n';
    output << "max_iterations\t" << max_iterations << '\n';
    output << "E0\t" << E0 << '\n';
    output << "E0_per_site\t" << E0 / Nsites_int << '\n';
    output << "D_raw_eigenvector\t" << D_eigenvector << '\n';
    output << "D_convention\t"
           << (factorized_free_limit ? "factorized_free_spin_sectors" : "ground_state_eigenvector")
           << '\n';
    output << "D\t" << D << '\n';
    output << "status\tCOMPLETE\n";
    output.close();

    std::cout << "E0 =      " << E0 << '\n'
              << "D =       " << D << '\n'
              << "status =  COMPLETE" << std::endl;
    return 0;
}
