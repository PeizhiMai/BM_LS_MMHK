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

// Ground-state-only spinless t-V solver at the 4x4 MMHK mixing resolution.
// The local Hilbert space is {|0>,|1>}; consequently there is no Hubbard-U
// term.  The physical half-filled benchmark uses N=8 particles on 16 internal
// orbitals and averages over the continuous mixed-momentum sector f.
int main(int argc, char* argv[]) {
    if (argc < 8) {
        std::cerr << "Usage: " << argv[0]
                  << " N kx ky qx qy V tp [seed]\n"
                  << "Use qx=qy=-1 to diagonalize the complete fixed-N "
                     "Hilbert space and minimize over all momentum sectors."
                  << std::endl;
        return 1;
    }

    const int N_input = std::atoi(argv[1]);
    const int kx = std::atoi(argv[2]);
    const int ky = std::atoi(argv[3]);
    const int Qm = std::atoi(argv[4]);
    const int Qn = std::atoi(argv[5]);
    const bool minimize_all_momenta = (Qm == -1 && Qn == -1);
    const double V = std::atof(argv[6]);
    const double tp = std::atof(argv[7]);
    const unsigned int seed =
        (argc >= 9) ? static_cast<unsigned int>(std::strtoul(argv[8], nullptr, 10)) : 1U;
    std::srand(seed);

    qbasis::initialize();
    std::cout << std::setprecision(12);

    constexpr double t = 1.0;
    constexpr int Lx = 4;
    constexpr int Ly = 4;
    constexpr int Nsites = Lx * Ly;
    constexpr MKL_INT max_iterations = 10000;
    const double N_value = static_cast<double>(N_input);

    if (N_input <= 0 || N_input > Nsites) {
        std::cerr << "N must satisfy 1 <= N <= " << Nsites << std::endl;
        return 2;
    }
    if ((Qm == -1) != (Qn == -1)) {
        std::cerr << "qx and qy must either both be -1 or both specify a "
                     "momentum sector"
                  << std::endl;
        return 3;
    }

    // Match the mixed-momentum grid convention used in the spinful solver.
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

    std::vector<std::string> bc{"pbc", "pbc"};
    qbasis::lattice lattice(
        "square", {static_cast<uint32_t>(Lx), static_cast<uint32_t>(Ly)}, bc);

    // Spinless fermion annihilation matrix in the local {|0>,|1>} basis.
    auto c = std::vector<std::vector<std::complex<double>>>(
        2, std::vector<std::complex<double>>(2, 0.0));
    c[0][1] = std::complex<double>(1.0, 0.0);

    qbasis::model<std::complex<double>> model(lattice);
    model.add_orbital(lattice.Nsites, "spinless-fermion");
    qbasis::mopr<std::complex<double>> Ntotal;

    for (int x = 0; x < Lx; ++x) {
        for (int y = 0; y < Ly; ++y) {
            uint32_t site_i;
            uint32_t site_j;
            std::vector<int> work(lattice.dim);
            lattice.coor2site({x, y}, 0, site_i, work);

            auto c_i = qbasis::opr<std::complex<double>>(site_i, 0, true, c);
            auto c_dg_i = c_i;
            c_dg_i.dagger();
            auto n_i = c_dg_i * c_i;
            Ntotal += n_i;

            lattice.coor2site({x + 1, y}, 0, site_j, work);
            auto c_jx = qbasis::opr<std::complex<double>>(site_j, 0, true, c);
            auto c_dg_jx = c_jx;
            c_dg_jx.dagger();
            auto n_jx = c_dg_jx * c_jx;
            model.add_Ham(std::complex<double>(-t * cx, -t * sx) * (c_dg_i * c_jx));
            model.add_Ham(std::complex<double>(-t * cx, t * sx) * (c_dg_jx * c_i));
            model.add_Ham(std::complex<double>(V, 0.0) * (n_i * n_jx));

            lattice.coor2site({x, y + 1}, 0, site_j, work);
            auto c_jy = qbasis::opr<std::complex<double>>(site_j, 0, true, c);
            auto c_dg_jy = c_jy;
            c_dg_jy.dagger();
            auto n_jy = c_dg_jy * c_jy;
            model.add_Ham(std::complex<double>(-t * cy, -t * sy) * (c_dg_i * c_jy));
            model.add_Ham(std::complex<double>(-t * cy, t * sy) * (c_dg_jy * c_i));
            model.add_Ham(std::complex<double>(V, 0.0) * (n_i * n_jy));

            lattice.coor2site({x + 1, y + 1}, 0, site_j, work);
            auto c_jpp = qbasis::opr<std::complex<double>>(site_j, 0, true, c);
            auto c_dg_jpp = c_jpp;
            c_dg_jpp.dagger();
            model.add_Ham(
                std::complex<double>(-tp * cxpy, -tp * sxpy) * (c_dg_i * c_jpp));
            model.add_Ham(
                std::complex<double>(-tp * cxpy, tp * sxpy) * (c_dg_jpp * c_i));

            lattice.coor2site({x + 1, y - 1}, 0, site_j, work);
            auto c_jpm = qbasis::opr<std::complex<double>>(site_j, 0, true, c);
            auto c_dg_jpm = c_jpm;
            c_dg_jpm.dagger();
            model.add_Ham(
                std::complex<double>(-tp * cxmy, -tp * sxmy) * (c_dg_i * c_jpm));
            model.add_Ham(
                std::complex<double>(-tp * cxmy, tp * sxmy) * (c_dg_jpm * c_i));
        }
    }

    Ntotal.simplify();
    model.fill_Weisse_table();
    MKL_INT basis_dimension = 0;
    if (minimize_all_momenta) {
        // A benchmark of the ground-state energy should not assume its total
        // momentum.  The full fixed-N basis automatically minimizes over all
        // 16 translation sectors at the present 4x4 mixing resolution.
        model.enumerate_basis_full({Ntotal}, {N_value});
        model.generate_Ham_sparse_full();
        model.locate_E0_lanczos(qbasis::which_sym::full, 1, 1, max_iterations);
        basis_dimension = model.dim_full[0];
    } else {
        model.enumerate_basis_repr({Qm, Qn}, {Ntotal}, {N_value});
        model.generate_Ham_sparse_repr();
        model.locate_E0_lanczos(qbasis::which_sym::repr, 1, 1, max_iterations);
        basis_dimension = model.dim_repr[0];
    }

    const double E0 = model.energy_min();
    const std::string output_name =
        "L" + std::to_string(Lx) + "x" + std::to_string(Ly) +
        "N" + std::to_string(N_input) + "V" + format_parameter(V) +
        "tp" + format_parameter(tp) + "f" + std::to_string(kx) + "x" +
        std::to_string(ky) +
        (minimize_all_momenta
             ? "Qall"
             : "Q" + std::to_string(Qm) + "x" + std::to_string(Qn)) +
        "_E0_spinless.dat";

    std::ofstream output(output_name, std::ios::out);
    output << std::scientific << std::setprecision(18);
    output << "Lx\t" << Lx << '\n';
    output << "Ly\t" << Ly << '\n';
    output << "N\t" << N_input << '\n';
    output << "V\t" << V << '\n';
    output << "tp\t" << tp << '\n';
    output << "kx\t" << kx << '\n';
    output << "ky\t" << ky << '\n';
    output << "Qx\t" << Qm << '\n';
    output << "Qy\t" << Qn << '\n';
    output << "momentum_treatment\t"
           << (minimize_all_momenta ? "all_sectors" : "fixed_sector") << '\n';
    output << "seed\t" << seed << '\n';
    output << "max_iterations\t" << max_iterations << '\n';
    output << "basis_dimension\t" << basis_dimension << '\n';
    output << "E0\t" << E0 << '\n';
    output << "E0_per_site\t" << E0 / Nsites << '\n';
    output << "E0_per_particle\t" << E0 / N_value << '\n';
    output << "status\tCOMPLETE\n";
    output.close();

    std::cout << "E0 =      " << E0 << '\n'
              << "E0/site = " << E0 / Nsites << '\n'
              << "E0/N =    " << E0 / N_value << '\n'
              << "dim =     " << basis_dimension << '\n'
              << "momentum = "
              << (minimize_all_momenta ? "all sectors" : "fixed sector") << '\n'
              << "status =  COMPLETE" << std::endl;
    return 0;
}
