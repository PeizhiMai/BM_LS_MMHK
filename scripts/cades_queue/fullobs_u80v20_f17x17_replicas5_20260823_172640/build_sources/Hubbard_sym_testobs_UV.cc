#include <cassert>
#include <iostream>
#include <iomanip>
#include "qbasis.h"
#include <cmath>
#include <fstream>
#include <sstream>
#include <cstdlib>  // For std::atoi, std::atof

#define PI 3.1415926535897932

// Extended Hubbard model on square lattice
int main(int argc, char *argv[]) {
    // Check if at least two arguments are provided (not counting the program name)
    if (argc < 10) {
        std::cerr << "Usage: " << argv[0] << "N_up N_dn <kx> <ky> qx qy U V tp" << std::endl;
        return 1;
    }

    // Read the first two command-line arguments into kx and ky
    int Nupinput = std::atoi(argv[1]);
    int Ndninput = std::atoi(argv[2]);
    int kx = std::atoi(argv[3]);  // Convert the first argument to an integer
    int ky = std::atoi(argv[4]);  // Convert the second argument to an integer
    int Qm = std::atoi(argv[5]);  // Convert the third argument to an integer
    int Qn = std::atoi(argv[6]);  // Convert the fourth argument to an integer
    double U = std::atof(argv[7]);
    double V = std::atof(argv[8]);
    double tp = std::atof(argv[9]);

    qbasis::initialize();
    std::cout << std::setprecision(10);
    // parameters
    double t = 1;
    int Lx = 4;
    int Ly = 4;
    double Nup_total = 1.0*Nupinput;
    double Ndn_total = 1.0*Ndninput;

    double fx = kx * PI/40+0.00001;
    double fy = ky * PI/40+0.00001;
    double sx = sin(fx);
    double cx = cos(fx);
    double sy = sin(fy);
    double cy = cos(fy);
    double cxpy = cos(fx+fy);
    double sxpy = sin(fx+fy);
    double cxmy = cos(fx-fy);
    double sxmy = sin(fx-fy);

    //int step = 150;

    std::cout << "Lx =      " << Lx << std::endl;
    std::cout << "Ly =      " << Ly << std::endl;
    std::cout << "t =       " << t << std::endl;
    std::cout << "tp =      " << tp << std::endl;
    std::cout << "U =       " << U << std::endl;
    std::cout << "V =       " << V << std::endl;
    std::cout << "kx =      " << kx << std::endl;
    std::cout << "ky =      " << ky << std::endl;
    std::cout << "N_up =    " << Nup_total << std::endl;
    std::cout << "N_dn =    " << Ndn_total << std::endl << std::endl;
    auto format_par = [](double val) {
        std::ostringstream ss;
        ss << std::defaultfloat << std::setprecision(6) << val;
        return ss.str();
    };
    std::string Ustr = format_par(U);
    std::string Vstr = format_par(V);
    std::string tpstr = format_par(tp);

    // lattice object
    std::vector<std::string> bc{"pbc", "pbc"};
    qbasis::lattice lattice("square",{static_cast<uint32_t>(Lx), static_cast<uint32_t>(Ly)},bc);


    // local matrix representation
    auto c_up = std::vector<std::vector<std::complex<double>>>(4,std::vector<std::complex<double>>(4, 0.0));
    auto c_dn = std::vector<std::vector<std::complex<double>>>(4,std::vector<std::complex<double>>(4, 0.0));
    c_up[0][1] = std::complex<double>(1.0,0.0);
    c_up[2][3] = std::complex<double>(1.0,0.0);
    c_dn[0][2] = std::complex<double>(1.0,0.0);
    c_dn[1][3] = std::complex<double>(-1.0,0.0);


    // constructing the Hamiltonian in operator representation
    qbasis::model<std::complex<double>> Hubbard(lattice);
    Hubbard.add_orbital(lattice.Nsites, "electron");
    qbasis::mopr<std::complex<double>> Nup;   // an operator representating total electron number
    qbasis::mopr<std::complex<double>> Ndown;
    for (int x = 0; x < Lx; x++) {
        for (int y = 0; y < Ly; y++) {
            uint32_t site_i, site_j;
            std::vector<int> work(lattice.dim);
            lattice.coor2site({x,y}, 0, site_i, work); // obtain site label of (x,y)
            // construct operators on each site
            auto c_up_i    = qbasis::opr<std::complex<double>>(site_i,0,true,c_up);
            auto c_dn_i    = qbasis::opr<std::complex<double>>(site_i,0,true,c_dn);
            auto c_up_dg_i = c_up_i; c_up_dg_i.dagger();
            auto c_dn_dg_i = c_dn_i; c_dn_dg_i.dagger();
            auto n_up_i    = c_up_dg_i * c_up_i;
            auto n_dn_i    = c_dn_dg_i * c_dn_i;
            auto n_i       = n_up_i + n_dn_i;

            // hopping to neighbor (x+1, y)
            if (bc[0] == "pbc" || (bc[0] == "obc" && x < Lx - 1)) {
                lattice.coor2site({x+1,y}, 0, site_j, work);
                auto c_up_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
                auto c_dn_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
                auto c_up_dg_j = c_up_j; c_up_dg_j.dagger();
                auto c_dn_dg_j = c_dn_j; c_dn_dg_j.dagger();
                auto n_up_j    = c_up_dg_j * c_up_j;
                auto n_dn_j    = c_dn_dg_j * c_dn_j;
                auto n_j       = n_up_j + n_dn_j;
                Hubbard.add_Ham(std::complex<double>(-t*cx,-t*sx) * ( c_up_dg_i * c_up_j ));
                Hubbard.add_Ham(std::complex<double>(-t*cx,t*sx ) * ( c_up_dg_j * c_up_i ));
                Hubbard.add_Ham(std::complex<double>(-t*cx,-t*sx) * ( c_dn_dg_i * c_dn_j ));
                Hubbard.add_Ham(std::complex<double>(-t*cx,t*sx ) * ( c_dn_dg_j * c_dn_i ));
                Hubbard.add_Ham(std::complex<double>(V,0.0) * (n_i * n_j));
            }

            // hopping to neighbor (x, y+1)
            if (bc[1] == "pbc" || (bc[1] == "obc" && y < Ly - 1)) {
                lattice.coor2site({x,y+1}, 0, site_j, work);
                auto c_up_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
                auto c_dn_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
                auto c_up_dg_j = c_up_j; c_up_dg_j.dagger();
                auto c_dn_dg_j = c_dn_j; c_dn_dg_j.dagger();
                auto n_up_j    = c_up_dg_j * c_up_j;
                auto n_dn_j    = c_dn_dg_j * c_dn_j;
                auto n_j       = n_up_j + n_dn_j;
                Hubbard.add_Ham(std::complex<double>(-t*cy,-t*sy) * ( c_up_dg_i * c_up_j ));
                Hubbard.add_Ham(std::complex<double>(-t*cy,t*sy ) * ( c_up_dg_j * c_up_i ));
                Hubbard.add_Ham(std::complex<double>(-t*cy,-t*sy) * ( c_dn_dg_i * c_dn_j ));
                Hubbard.add_Ham(std::complex<double>(-t*cy,t*sy ) * ( c_dn_dg_j * c_dn_i ));
                Hubbard.add_Ham(std::complex<double>(V,0.0) * (n_i * n_j));
            }

            // hopping to second neighbor (x+1, y+1)
            if (bc[0] == "pbc" || (bc[0] == "obc" && x < Lx - 1 && y < Ly - 1)) {
                lattice.coor2site({x+1,y+1}, 0, site_j, work);
                auto c_up_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
                auto c_dn_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
                auto c_up_dg_j = c_up_j; c_up_dg_j.dagger();
                auto c_dn_dg_j = c_dn_j; c_dn_dg_j.dagger();
                Hubbard.add_Ham(std::complex<double>(-tp*cxpy,-tp*sxpy) * ( c_up_dg_i * c_up_j ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxpy,tp*sxpy ) * ( c_up_dg_j * c_up_i ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxpy,-tp*sxpy) * ( c_dn_dg_i * c_dn_j ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxpy,tp*sxpy ) * ( c_dn_dg_j * c_dn_i ));
            }

            if (bc[0] == "pbc" || (bc[0] == "obc" && x < Lx - 1 && y < Ly - 1 && y > 0)) {
                lattice.coor2site({x+1,y-1}, 0, site_j, work);
                auto c_up_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
                auto c_dn_j    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
                auto c_up_dg_j = c_up_j; c_up_dg_j.dagger();
                auto c_dn_dg_j = c_dn_j; c_dn_dg_j.dagger();
                Hubbard.add_Ham(std::complex<double>(-tp*cxmy,-tp*sxmy) * ( c_up_dg_i * c_up_j ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxmy,tp*sxmy ) * ( c_up_dg_j * c_up_i ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxmy,-tp*sxmy) * ( c_dn_dg_i * c_dn_j ));
                Hubbard.add_Ham(std::complex<double>(-tp*cxmy,tp*sxmy ) * ( c_dn_dg_j * c_dn_i ));
            }

            // Hubbard repulsion, note that this operator is a sum (over sites) of diagonal matrices
            Hubbard.add_Ham(std::complex<double>(U,0.0) * (n_up_i * n_dn_i));

            // total electron operator
            Nup   += n_up_i;
            Ndown += n_dn_i;
        }
    }


    // Equal-time observables measured after the fixed-(N_up,N_down,Q) ground
    // state has been obtained.  These operators are kept separate from the
    // Hamiltonian construction above so that adding measurements cannot alter
    // the production Hamiltonian.
    //
    // Normalizations used below:
    //   nn_density_sum = sum_<ij> n_i n_j, each NN bond counted once;
    //   spin_nn_sum    = sum_<ij> S_i.S_j, each NN bond counted once;
    //   kinetic_*      = the corresponding terms in the Hamiltonian;
    //   charge_pipi    = (1/sqrt(N)) sum_i (-1)^(x_i+y_i) n_i.
    qbasis::mopr<std::complex<double>> nn_density_sum;
    qbasis::mopr<std::complex<double>> spin_nn_sum;
    qbasis::mopr<std::complex<double>> kinetic_nn;
    qbasis::mopr<std::complex<double>> kinetic_nnn;
    qbasis::mopr<std::complex<double>> charge_pipi;
    int num_nn_bonds = 0;
    const double inv_sqrt_Nsites = 1.0 / std::sqrt(static_cast<double>(Lx * Ly));

    for (int x = 0; x < Lx; x++) {
        for (int y = 0; y < Ly; y++) {
            uint32_t site_i, site_j;
            std::vector<int> work(lattice.dim);
            lattice.coor2site({x,y}, 0, site_i, work);

            auto c_up_i    = qbasis::opr<std::complex<double>>(site_i,0,true,c_up);
            auto c_dn_i    = qbasis::opr<std::complex<double>>(site_i,0,true,c_dn);
            auto c_up_dg_i = c_up_i; c_up_dg_i.dagger();
            auto c_dn_dg_i = c_dn_i; c_dn_dg_i.dagger();
            auto n_up_i    = c_up_dg_i * c_up_i;
            auto n_dn_i    = c_dn_dg_i * c_dn_i;
            auto n_i       = n_up_i + n_dn_i;
            auto sz_i      = std::complex<double>(0.5,0.0) * (n_up_i - n_dn_i);
            auto sp_i      = c_up_dg_i * c_dn_i;
            auto sm_i      = c_dn_dg_i * c_up_i;

            const double staggered_sign = ((x + y) % 2 == 0) ? 1.0 : -1.0;
            charge_pipi += std::complex<double>(staggered_sign * inv_sqrt_Nsites,0.0) * n_i;

            // Nearest-neighbor bond in +x direction.
            lattice.coor2site({x+1,y}, 0, site_j, work);
            auto c_up_j_x    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
            auto c_dn_j_x    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
            auto c_up_dg_j_x = c_up_j_x; c_up_dg_j_x.dagger();
            auto c_dn_dg_j_x = c_dn_j_x; c_dn_dg_j_x.dagger();
            auto n_up_j_x    = c_up_dg_j_x * c_up_j_x;
            auto n_dn_j_x    = c_dn_dg_j_x * c_dn_j_x;
            auto n_j_x       = n_up_j_x + n_dn_j_x;
            auto sz_j_x      = std::complex<double>(0.5,0.0) * (n_up_j_x - n_dn_j_x);
            auto sp_j_x      = c_up_dg_j_x * c_dn_j_x;
            auto sm_j_x      = c_dn_dg_j_x * c_up_j_x;

            nn_density_sum += n_i * n_j_x;
            spin_nn_sum += sz_i * sz_j_x
                         + std::complex<double>(0.5,0.0) * (sp_i * sm_j_x + sm_i * sp_j_x);
            kinetic_nn += std::complex<double>(-t*cx,-t*sx) * (c_up_dg_i * c_up_j_x);
            kinetic_nn += std::complex<double>(-t*cx, t*sx) * (c_up_dg_j_x * c_up_i);
            kinetic_nn += std::complex<double>(-t*cx,-t*sx) * (c_dn_dg_i * c_dn_j_x);
            kinetic_nn += std::complex<double>(-t*cx, t*sx) * (c_dn_dg_j_x * c_dn_i);
            num_nn_bonds++;

            // Nearest-neighbor bond in +y direction.
            lattice.coor2site({x,y+1}, 0, site_j, work);
            auto c_up_j_y    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
            auto c_dn_j_y    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
            auto c_up_dg_j_y = c_up_j_y; c_up_dg_j_y.dagger();
            auto c_dn_dg_j_y = c_dn_j_y; c_dn_dg_j_y.dagger();
            auto n_up_j_y    = c_up_dg_j_y * c_up_j_y;
            auto n_dn_j_y    = c_dn_dg_j_y * c_dn_j_y;
            auto n_j_y       = n_up_j_y + n_dn_j_y;
            auto sz_j_y      = std::complex<double>(0.5,0.0) * (n_up_j_y - n_dn_j_y);
            auto sp_j_y      = c_up_dg_j_y * c_dn_j_y;
            auto sm_j_y      = c_dn_dg_j_y * c_up_j_y;

            nn_density_sum += n_i * n_j_y;
            spin_nn_sum += sz_i * sz_j_y
                         + std::complex<double>(0.5,0.0) * (sp_i * sm_j_y + sm_i * sp_j_y);
            kinetic_nn += std::complex<double>(-t*cy,-t*sy) * (c_up_dg_i * c_up_j_y);
            kinetic_nn += std::complex<double>(-t*cy, t*sy) * (c_up_dg_j_y * c_up_i);
            kinetic_nn += std::complex<double>(-t*cy,-t*sy) * (c_dn_dg_i * c_dn_j_y);
            kinetic_nn += std::complex<double>(-t*cy, t*sy) * (c_dn_dg_j_y * c_dn_i);
            num_nn_bonds++;

            // Next-nearest-neighbor kinetic terms are included so that the
            // reported total kinetic energy remains correct when tp != 0.
            lattice.coor2site({x+1,y+1}, 0, site_j, work);
            auto c_up_j_pp    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
            auto c_dn_j_pp    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
            auto c_up_dg_j_pp = c_up_j_pp; c_up_dg_j_pp.dagger();
            auto c_dn_dg_j_pp = c_dn_j_pp; c_dn_dg_j_pp.dagger();
            kinetic_nnn += std::complex<double>(-tp*cxpy,-tp*sxpy) * (c_up_dg_i * c_up_j_pp);
            kinetic_nnn += std::complex<double>(-tp*cxpy, tp*sxpy) * (c_up_dg_j_pp * c_up_i);
            kinetic_nnn += std::complex<double>(-tp*cxpy,-tp*sxpy) * (c_dn_dg_i * c_dn_j_pp);
            kinetic_nnn += std::complex<double>(-tp*cxpy, tp*sxpy) * (c_dn_dg_j_pp * c_dn_i);

            lattice.coor2site({x+1,y-1}, 0, site_j, work);
            auto c_up_j_pm    = qbasis::opr<std::complex<double>>(site_j,0,true,c_up);
            auto c_dn_j_pm    = qbasis::opr<std::complex<double>>(site_j,0,true,c_dn);
            auto c_up_dg_j_pm = c_up_j_pm; c_up_dg_j_pm.dagger();
            auto c_dn_dg_j_pm = c_dn_j_pm; c_dn_dg_j_pm.dagger();
            kinetic_nnn += std::complex<double>(-tp*cxmy,-tp*sxmy) * (c_up_dg_i * c_up_j_pm);
            kinetic_nnn += std::complex<double>(-tp*cxmy, tp*sxmy) * (c_up_dg_j_pm * c_up_i);
            kinetic_nnn += std::complex<double>(-tp*cxmy,-tp*sxmy) * (c_dn_dg_i * c_dn_j_pm);
            kinetic_nnn += std::complex<double>(-tp*cxmy, tp*sxmy) * (c_dn_dg_j_pm * c_dn_i);
        }
    }

    nn_density_sum.simplify();
    spin_nn_sum.simplify();
    kinetic_nn.simplify();
    kinetic_nnn.simplify();
    charge_pipi.simplify();


    // to use translational symmetry, we first fill the Weisse tables
    Hubbard.fill_Weisse_table();


    // measure operators

    std::vector<double> E0_list;
    for (int m = 0; m < 1; m++) {
        for (int n = 0; n < 1; n++) {
            
            // constructing the Hilbert space basis
            Hubbard.enumerate_basis_repr({Qm,Qn}, {Nup,Ndown}, {Nup_total,Ndn_total});

            // generating matrix of the Hamiltonian in the subspace
            Hubbard.generate_Ham_sparse_repr();
            std::cout << std::endl;

            // obtaining the lowest eigenvals of the matrix
            // The all-twist U=40 scan contains difficult sectors that can
            // exhaust the reviewed 10,000-step limit. Keep one requested
            // eigenpair and the same one-vector setting, but raise only the
            // Lanczos/CG iteration ceiling for this convergence-hardened run.
            Hubbard.locate_E0_lanczos(qbasis::which_sym::repr, 1, 1, 50000);
            std::cout << std::endl;

            E0_list.push_back(Hubbard.eigenvals_repr[0]);

            
        }
    }

    // prepare list of momentum points for measurement
    std::vector<std::vector<int>> q_list;
    for (int m = 0; m < 1; m++) {
        for (int n = 0; n < 1; n++) {
            q_list.push_back({m,n});
        }
    }

    std::string output_name_p = "L"+std::to_string(Lx)+"x"+std::to_string(Ly)+"Nup"+std::to_string(int(Nup_total))+"Ndn"+std::to_string(int(Ndn_total))+"U"+Ustr+"V"+Vstr+"tp"+tpstr+"f"+std::to_string(kx)+"x"+std::to_string(ky)+"Q"+std::to_string(Qm)+"x"+std::to_string(Qn)+"_obs.dat";
    std::ofstream fout_p(output_name_p, std::ios::out);
    fout_p << std::scientific << std::right;
    fout_p << std::setprecision(18);
    fout_p << "Lx\t" << Lx << std::endl;
    fout_p << "Ly\t" << Ly << std::endl;
    fout_p << "tp\t" << tp << std::endl;
    fout_p << "U\t" << U << std::endl;
    fout_p << "V\t" << V << std::endl;
    fout_p << "E0\t" << Hubbard.energy_min() << std::endl;
    fout_p << "Gap\t" << Hubbard.energy_gap() << std::endl << std::endl;


    // Static, zero-momentum observables.  As in the existing real-space
    // double-occupancy estimator, N_tot|psi> = N_tot*|psi> supplies the
    // reference ground-state vector without leaving the fixed-Q basis.
    MKL_INT which_col_static = 0;
    auto Ntotal_op = Nup + Ndown;
    Ntotal_op.simplify();
    std::vector<std::complex<double>> vec_number(Hubbard.dim_repr[0]);
    Hubbard.moprXvec_repr(Ntotal_op, 0, 0, which_col_static, vec_number.data());

    auto measure_zero_momentum = [&](qbasis::mopr<std::complex<double>>& op) {
        std::vector<std::complex<double>> vec_op(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(op, 0, 0, which_col_static, vec_op.data());
        std::complex<double> value = 0.0;
        for (int ix = 0; ix < Hubbard.dim_repr[0]; ix++) {
            value += std::conj(vec_number[ix]) * vec_op[ix];
        }
        return value / (Nup_total + Ndn_total);
    };

    auto kinetic_total = kinetic_nn + kinetic_nnn;
    kinetic_total.simplify();
    const double Nsites = static_cast<double>(Lx * Ly);
    const double density = (Nup_total + Ndn_total) / Nsites;
    const double nn_density = std::real(measure_zero_momentum(nn_density_sum))
                            / static_cast<double>(num_nn_bonds);
    const double C1 = std::real(measure_zero_momentum(spin_nn_sum))
                    / static_cast<double>(num_nn_bonds);
    const double kinetic_nn_per_site = std::real(measure_zero_momentum(kinetic_nn)) / Nsites;
    const double kinetic_nnn_per_site = std::real(measure_zero_momentum(kinetic_nnn)) / Nsites;
    const double kinetic_per_site = std::real(measure_zero_momentum(kinetic_total)) / Nsites;

    fout_p << "<nn_NN> " << nn_density << std::endl;
    fout_p << "<delta_n_delta_n_NN> " << nn_density - density * density << std::endl;
    fout_p << "<Kinetic_NN_per_site> " << kinetic_nn_per_site << std::endl;
    fout_p << "<Kinetic_NNN_per_site> " << kinetic_nnn_per_site << std::endl;
    fout_p << "<Kinetic_per_site> " << kinetic_per_site << std::endl;
    fout_p << "<C1_NN> " << C1 << std::endl;

    // loop over all the q points
    for (auto q : q_list) {
        int m = q[0];
        int n = q[1];
        std::cout << "k\t" << m << "," << n << std::endl;
        fout_p << "Q\t" << m << "," << n << std::endl;

        // construct c_up(q) and c_up^\dagger(q)
        qbasis::mopr<std::complex<double>> c_up_q, c_up_dg_q, c_dn_q, c_dn_dg_q, n_up_q, n_dn_q, n_q, n_q2;
	qbasis::mopr<std::complex<double>> n_up_i_spe, n_dn_i_spe;
        std::complex<double> m1 = 0, m2 = 0, m3 = 0;

        for (int x = 0; x < Lx; x++) {
            for (int y = 0; y < Ly; y++) {
                double qdotr = 2.0 * PI * (m * x / static_cast<double>(Lx) + n * y / static_cast<double>(Ly));
                auto coeff = 1.0 / sqrt(static_cast<double>(Lx * Ly)) * std::exp(std::complex<double>{0.0,qdotr});
                auto coeffm = 1.0 / sqrt(static_cast<double>(Lx * Ly)) * std::exp(std::complex<double>{0.0,-qdotr});
                uint32_t site;
                std::vector<int> work(lattice.dim);
                lattice.coor2site({x,y}, 0, site, work);
                auto c_up_i    = qbasis::opr<std::complex<double>>(site,0,true,c_up);
                auto c_up_dg_i = c_up_i; c_up_dg_i.dagger();
                c_up_q += coeff * c_up_i;
                c_up_dg_q += coeffm * c_up_dg_i;
                
                auto c_dn_i    = qbasis::opr<std::complex<double>>(site,0,true,c_dn);
                auto c_dn_dg_i = c_dn_i; c_dn_dg_i.dagger();
                c_dn_q += coeff * c_dn_i;
                c_dn_dg_q += coeffm * c_dn_dg_i;


	        n_up_i_spe += c_up_dg_i * c_up_i * c_dn_dg_i * c_dn_i;
		n_dn_i_spe += (c_dn_dg_i * c_dn_i + c_up_dg_i * c_up_i);
                
            }
        }
        c_up_q.simplify();
        c_up_dg_q.simplify();
        Hubbard.enumerate_basis_repr({Qm-m,Qn-n}, {Nup,Ndown}, {Nup_total-1,Ndn_total},1);
        std::vector<std::complex<double>> vec_newcup(Hubbard.dim_repr[1]);
        MKL_INT which_col = 0;
        Hubbard.moprXvec_repr(c_up_q, 0, 1, which_col, vec_newcup.data());
        
        c_dn_q.simplify();
        c_dn_dg_q.simplify();
        Hubbard.enumerate_basis_repr({Qm-m,Qn-n}, {Nup,Ndown}, {Nup_total,Ndn_total-1},2);
        std::vector<std::complex<double>> vec_newcdn(Hubbard.dim_repr[2]);
        Hubbard.moprXvec_repr(c_dn_q, 0, 2, which_col, vec_newcdn.data());

        
        n_up_q = c_up_dg_q * c_up_q;
        n_dn_q = c_dn_dg_q * c_dn_q;
        n_up_q.simplify();
        n_dn_q.simplify();
        std::vector<std::complex<double>> vec_newnup(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(n_up_q, 0, 0, which_col, vec_newnup.data());
        std::vector<std::complex<double>> vec_newndn(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(n_dn_q, 0, 0, which_col, vec_newndn.data());

        for (int ix = 0; ix < Hubbard.dim_repr[1]; ix++) {
            m1 += std::conj(vec_newcup[ix]) * vec_newcup[ix] + std::conj(vec_newcdn[ix]) * vec_newcdn[ix];
            }
        
        for (int ix = 0; ix < Hubbard.dim_repr[0]; ix++) {
            m2 += std::conj(vec_newnup[ix]) * vec_newndn[ix];
            }

        
        n_up_i_spe.simplify();
        n_dn_i_spe.simplify();
        std::vector<std::complex<double>> vec_newnup_spec(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(n_up_i_spe, 0, 0, which_col, vec_newnup_spec.data());
        std::vector<std::complex<double>> vec_newndn_spec(Hubbard.dim_repr[0]);
        Hubbard.moprXvec_repr(n_dn_i_spe, 0, 0, which_col, vec_newndn_spec.data());

	for (int ix = 0; ix < Hubbard.dim_repr[0]; ix++) {
            m3 += std::conj(vec_newnup_spec[ix]) * vec_newndn_spec[ix] / (1.0*Lx) / (1.0*Ly)/ (Nup_total + Ndn_total);
            }

        fout_p << "<nq> " << std::real(m1) << std::endl;
        fout_p << "<nq_upnq_dn> " << std::real(m2) << std::endl;
        std::cout << std::endl;

        fout_p << "<ni_upni_dn> " << std::real(m3) << std::endl;
        std::cout << std::endl;

        // Calculate S^zz(pi,pi) and S_c(pi,pi) in the same target momentum
        // basis, avoiding a second expensive basis enumeration.
        qbasis::mopr<std::complex<double>> s_pipi;
        int mq = Lx / 2;
        int nq = Ly / 2;
        for (int x = 0; x < Lx; x++) {
            for (int y = 0; y < Ly; y++) {
                double qdotr = 2.0 * PI * (mq * x / static_cast<double>(Lx) + nq * y / static_cast<double>(Ly));
                auto coeff = 0.5 * 1.0 / sqrt(static_cast<double>(Lx * Ly)) * std::exp(std::complex<double>{0.0, qdotr});
                uint32_t site;
                std::vector<int> work(lattice.dim);
                lattice.coor2site({x, y}, 0, site, work);
                auto c_up_i = qbasis::opr<std::complex<double>>(site, 0, true, c_up);
                auto c_up_dg_i = c_up_i; c_up_dg_i.dagger();
                auto c_dn_i = qbasis::opr<std::complex<double>>(site, 0, true, c_dn);
                auto c_dn_dg_i = c_dn_i; c_dn_dg_i.dagger();

                s_pipi += coeff * (c_up_dg_i * c_up_i - c_dn_dg_i * c_dn_i);
            }
        }
        s_pipi.simplify();
        const int pipi_target_Qm = (Qm + mq) % Lx;
        const int pipi_target_Qn = (Qn + nq) % Ly;
        Hubbard.enumerate_basis_repr(
            {pipi_target_Qm, pipi_target_Qn},
            {Nup, Ndown},
            {Nup_total, Ndn_total},
            1
        );
        std::vector<std::complex<double>> vec_spipi(Hubbard.dim_repr[1]);
        Hubbard.moprXvec_repr(s_pipi, 0, 1, which_col, vec_spipi.data());
        std::complex<double> m_spipi = 0;
        for (int ix = 0; ix < Hubbard.dim_repr[1]; ix++) {
            m_spipi += std::conj(vec_spipi[ix]) * vec_spipi[ix];
        }
        fout_p << "<Spipi> " << std::real(m_spipi) << std::endl;

        // S_c(pi,pi) = ||rho_(pi,pi)|psi_Q>||^2 with
        // rho_(pi,pi)=(1/sqrt(N))*sum_i (-1)^(x_i+y_i)*(n_i-1).
        // The constant term cancels exactly on the even square lattice.
        std::vector<std::complex<double>> vec_charge_pipi(Hubbard.dim_repr[1]);
        Hubbard.moprXvec_repr(charge_pipi, 0, 1, which_col, vec_charge_pipi.data());
        std::complex<double> Sc_pipi = 0.0;
        for (int ix = 0; ix < Hubbard.dim_repr[1]; ix++) {
            Sc_pipi += std::conj(vec_charge_pipi[ix]) * vec_charge_pipi[ix];
        }
        fout_p << "<Sc_pipi> " << std::real(Sc_pipi) << std::endl;
        fout_p << "<mCDW2_pipi> " << std::real(Sc_pipi) / Nsites << std::endl;
        std::cout << std::endl;

                
    }
    // Written last so submission scripts can distinguish a complete observable
    // file from one left behind by a timeout or interrupted calculation.
    fout_p << "status\tCOMPLETE" << std::endl;
    fout_p.close();

}
