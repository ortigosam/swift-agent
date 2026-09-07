import Foundation

protocol CashbackRepository {
    func getCashback() async throws -> Cashback
}

protocol CashbackDataSource {
    func getCashback() async throws -> Cashback
}

struct Cashback {
    let amount: Decimal
}

final class CashbackRepositoryImpl: CashbackRepository {

    private let dataSource: CashbackDataSource

    init(dataSource: CashbackDataSource) {
        self.dataSource = dataSource
    }

    func getCashback() async throws -> Cashback {
        try await dataSource.getCashback()
    }
}

extension CashbackRepositoryImpl {
    func getAdditionalCashback() async throws -> Cashback {
        try await dataSource.getCashback()
    }
}
